---
issue: 145
title: Interactive guided continue session
repository: Modern-Ash/agora-ai-sdlc
status: implementing
risk: medium
created_at: 2026-09-21
---
# Task

Turn `agora-ai-sdlc continue` into a TTY-aware interactive guided session while preserving deterministic non-interactive modes.

## Acceptance
- TTY waits for user selection
- runtime chooser lists responsive detected CLIs
- selected runtime persists in-session
- runtime can be changed
- review/details/exit are actionable
- non-TTY and --non-interactive remain one-shot
- JSON/commands/expert remain non-interactive
- no approval is invented or auto-recorded
- full CI green
