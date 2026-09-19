---
name: wrong-name-on-purpose
description: 评测器自测用的坏样本。已知问题清单（selftest.py 按此对账断言）：1) name 与目录名不符（wrong-name-on-purpose != bad-skill）；2) 正文引用 references/ghost-file.md 不存在；3) frontmatter 藏 sk-abc123def456ghi789jklmnop 密钥；4) 正文藏 api_key = "AbCdEf123456GhIjKlMn" 字面量。任何一类抓不到都是 lint 的退化。注意 references/real-file.md 是真实存在的，防止误报也要被断言。
---

# Bad Skill（勿修）

正文引用 `references/ghost-file.md`（应报缺失）和 `references/real-file.md`（存在，不应报）。

凭据示例：api_key = "AbCdEf123456GhIjKlMn"
