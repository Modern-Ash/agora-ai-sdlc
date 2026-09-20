---
issue: 9
tested_commit: working tree on 1f896ec
timestamp: 2026-09-20
---
# Tests

## Environment
Linux, zsh, gh authenticated.

## Exact commands
- `git remote get-url origin`
- `gh issue view 1`
- `git clone https://github.com/Modern-Ash/agora-ai-sdlc.git <tmp>`
- grep for the dotted name across `*.md`; Python relative-link check on README.md and docs/terminology.md

## Cases executed / Result
All passed: origin has canonical name; issue history accessible; clone works; dotted name appears only in README migration note; no broken links.

## Cases not executed
macOS and Windows clone. Reason: not available; the commands are platform-neutral git/gh invocations.

## Evidence
Command output in session.
