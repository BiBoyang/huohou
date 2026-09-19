#!/usr/bin/env python3
"""skill-up custom-engine adapter for the Claude Code CLI.

Reads a skill-up SessionInput JSON, runs `claude -p --output-format
stream-json --verbose` in the case workspace, and writes a SessionResult
JSON using the same transcript contract as kimi_engine.py: assistant text,
tool_call (name + parsed arguments), tool_result (paired by id). Skill
activation is detectable from tool_call.name == "Skill" and
arguments.skill — identical shape to kimi, so trigger_report.py needs no
changes.

Isolation: each case gets its own CLAUDE_CONFIG_DIR under the workspace.
The user's ~/.claude/settings.json is copied with only the env block
(credentials, endpoint, model mappings) kept — hooks, statusLine, and
plugins are stripped so they cannot perturb the agent under test. Skills
installed by skill-up under <workspace>/skills are symlinked into the
isolated home's skills/ directory. The isolated home is deleted after the
run because the copied settings contain credentials.

Token usage: claude's final result event carries modelUsage per model;
input/output tokens are summed across models and reported in the
SessionResult top level (unlike kimi, where usage is unavailable).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

MAX_STDERR_CHARS = 4000
EVAL_HOME_NAME = ".claude-eval-home"
MAX_TURNS = "15"


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


def ensure_eval_home(workspace):
    """Create a per-case isolated CLAUDE_CONFIG_DIR; return its path."""
    home = os.path.join(workspace, EVAL_HOME_NAME)
    skills_dir = os.path.join(workspace, "skills")
    os.makedirs(os.path.join(home, "skills"), exist_ok=True)

    src_settings = os.path.expanduser("~/.claude/settings.json")
    with open(src_settings, encoding="utf-8") as f:
        settings = json.load(f)
    stripped = {"env": settings.get("env", {})}
    with open(os.path.join(home, "settings.json"), "w", encoding="utf-8") as f:
        json.dump(stripped, f, indent=1)

    if os.path.isdir(skills_dir):
        for name in os.listdir(skills_dir):
            src = os.path.join(skills_dir, name)
            dst = os.path.join(home, "skills", name)
            if os.path.isdir(src) and not os.path.exists(dst):
                os.symlink(src, dst)
    return home


def parse_stream_json(stdout):
    """Return (final_message, structured_events, usage) from claude output."""
    final = ""
    structured = []
    usage = {"input_tokens": 0, "output_tokens": 0}
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = ev.get("type")

        if etype == "assistant":
            for block in (ev.get("message") or {}).get("content") or []:
                if block.get("type") == "tool_use":
                    structured.append({
                        "role": "tool_call",
                        "tool_call": {
                            "id": block.get("id", ""),
                            "name": block.get("name", ""),
                            "arguments": block.get("input") or {},
                        },
                    })
                elif block.get("type") == "text" and block.get("text"):
                    structured.append({"role": "assistant", "content": block["text"]})
                    final = block["text"]
        elif etype == "user":
            content = (ev.get("message") or {}).get("content")
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        body = block.get("content")
                        if isinstance(body, list):
                            body = " ".join(str(b.get("text", "")) for b in body
                                            if isinstance(b, dict))
                        structured.append({
                            "role": "tool_result",
                            "tool_result": {
                                "call_id": block.get("tool_use_id", ""),
                                "content": str(body or ""),
                            },
                        })
        elif etype == "result":
            for model_usage in (ev.get("modelUsage") or {}).values():
                usage["input_tokens"] += model_usage.get("inputTokens") or 0
                usage["output_tokens"] += model_usage.get("outputTokens") or 0
            if not final and ev.get("result"):
                final = ev["result"]
        # system/init and other control events: not part of the conversation
    return final, structured, usage


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

    home = ensure_eval_home(workspace)
    env = dict(os.environ, CLAUDE_CONFIG_DIR=home)

    cmd = ["claude", "-p", prompt,
           "--output-format", "stream-json", "--verbose",
           "--max-turns", MAX_TURNS]

    started = time.time()
    # the isolated home holds copied credentials; the finally block is the
    # only acceptable exit path — a crash mid-run must never leave it on disk
    try:
        try:
            proc = subprocess.run(cmd, cwd=workspace, env=env,
                                  capture_output=True, text=True, timeout=timeout)
            exit_code = proc.returncode
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = exc.stdout or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", "replace")
            stderr = f"claude timed out after {timeout}s"
    finally:
        shutil.rmtree(home, ignore_errors=True)

    final_message, structured, usage = parse_stream_json(stdout)
    if not final_message:
        final_message = stdout.strip()
    result = {
        "exit_code": exit_code,
        "final_message": final_message,
        "stderr": stderr[-MAX_STDERR_CHARS:],
        "duration_ms": int((time.time() - started) * 1000),
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "transcript": messages + structured,
    }

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.exit(main())
