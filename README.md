# manage

Local-first desktop app where you play PM of an AI-powered hedge fund. Claude-backed investor personas, analysts, risk, and a PM produce research, debate theses, and backtest decisions.

Analytical / educational tool only. Executes no trades. See `CLAUDE.md` §14.

## Status

**Phase 3 — Committee Room.** Research Desk (persona + analyst stack → memo), Roster CRUD, and now a Committee Room (moderator → personas → risk → PM with a transcript + verdict). See `CLAUDE.md` §12 for the phased plan.

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
