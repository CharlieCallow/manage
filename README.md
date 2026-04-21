# manage

Local-first desktop app where you play PM of an AI-powered hedge fund. Claude-backed investor personas, analysts, risk, and a PM produce research, debate theses, and backtest decisions.

Analytical / educational tool only. Executes no trades. See `CLAUDE.md` §14.

## Status

**Phase 0 — Foundation.** Streaming debug panel over a hard-coded Buffett persona. See `CLAUDE.md` §12 for the phased plan.

## Quickstart

```bash
pnpm install
cd apps/backend && poetry install && cd ../..
cp .env.example .env            # then fill in ANTHROPIC_API_KEY

# Two terminals
pnpm dev:backend
pnpm dev:desktop
```

See `CLAUDE.md` for architecture, conventions, and safety rails.
