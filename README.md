# manage

Local-first desktop app where you play PM of an AI-powered hedge fund. Claude-backed investor personas, analysts, risk, and a PM produce research, debate theses, and backtest decisions.

Analytical / educational tool only. Executes no trades. See `CLAUDE.md` §14.

## Status

**Post-Phase-5 baseline.** All six rooms from the phased plan are live — Office (portfolio, spend, jobs), Research Desk, Committee Room, Trading Floor (ambient agent activity), Time Machine (time-stepped backtester + persona scoreboard), Roster — plus a seventh room, **Ideas**, where every persona surfaces candidate tickers you can approve into full research jobs. See `CLAUDE.md` §12.

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
