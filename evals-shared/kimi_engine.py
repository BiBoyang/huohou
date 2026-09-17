#!/usr/bin/env python3
"""skill-up custom-engine adapter for the kimi CLI.

Reads a skill-up SessionInput JSON, runs `kimi -p` (stream-json) in the case
workspace, and writes a SessionResult JSON. Skills installed by skill-up under
<workspace>/skills are exposed to kimi via --skills-dir.

Note: kimi -p does not accept --yolo/--auto; print mode already runs tools
non-interactively.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

MAX_STDERR_CHARS = 4000

# Isolated KIMI_CODE_HOME so user-level hooks (timestamp injection, bash
# auditing) do not perturb the agent under test or corrupt judge JSON output.
# Credentials are symlinked from the real home; config.toml is copied with
# [[hooks]] blocks stripped. Secrets never leave the local machine.
KIMI_EVAL_HOME = os.path.expanduser("~/.skill-up-kimi-home")


def ensure_eval_home():
    src_home = os.path.expanduser("~/.kimi-code")
    os.makedirs(KIMI_EVAL_HOME, exist_ok=True)

    src_config = os.path.join(src_home, "config.toml")
    dst_config = os.path.join(KIMI_EVAL_HOME, "config.toml")
    with open(src_config, encoding="utf-8") as f:
        text = f.read()
    stripped = re.sub(r"(?ms)^\[\[hooks\]\]\n.*?(?=^\[|\Z)", "", text)
    if not os.path.exists(dst_config) or open(dst_config, encoding="utf-8").read() != stripped:
        with open(dst_config, "w", encoding="utf-8") as f:
            f.write(stripped)

    for name in ("credentials", "oauth", "device_id", "mcp.json"):
        src = os.path.join(src_home, name)
        dst = os.path.join(KIMI_EVAL_HOME, name)
        if os.path.exists(src) and not os.path.exists(dst):
            os.symlink(src, dst)


def build_prompt(messages):
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "user":
            parts.append(content)
        elif role == "assistant":
            parts.append(f"[此前的助手回复]\n{content}")
        elif role == "system":
            parts.append(f"[系统]\n{content}")
    return "\n\n".join(p for p in parts if p.strip())


def parse_stream_json(stdout):
    """Return (final_message, transcript_tail) from kimi stream-json output."""
    final = ""
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = ev.get("role")
        if role == "assistant" and ev.get("content"):
            final = ev["content"]
            events.append({"role": "assistant", "content": ev["content"]})
        elif role == "tool":
            events.append({"role": "tool", "content": ev.get("content", "")})
    return final, events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        session_input = json.load(f)

    workspace = session_input.get("workspace") or os.getcwd()
    messages = session_input.get("messages") or []
    prompt = build_prompt(messages)
    timeout = int(session_input.get("timeout_seconds") or 600)

    cmd = ["kimi", "-p", prompt, "--output-format", "stream-json"]
    # Always pin --skills-dir: it replaces user/project skill auto-discovery.
    # In the without_skill variant skill-up installs nothing, so an empty dir
    # keeps the baseline genuinely skill-less.
    skills_dir = os.path.join(workspace, "skills")
    os.makedirs(skills_dir, exist_ok=True)
    cmd += ["--skills-dir", skills_dir]

    ensure_eval_home()
    env = dict(os.environ, KIMI_CODE_HOME=KIMI_EVAL_HOME)

    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        stderr = f"kimi timed out after {timeout}s"

    final_message, events = parse_stream_json(stdout)
    if not final_message:
        final_message = stdout.strip()
    result = {
        "exit_code": exit_code,
        "final_message": final_message,
        "stderr": stderr[-MAX_STDERR_CHARS:],
        "duration_ms": int((time.time() - started) * 1000),
        "transcript": messages + events,
    }

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.exit(main())
