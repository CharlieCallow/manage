"""Persona + analyst registry. CLAUDE.md §13."""
from __future__ import annotations

from collections.abc import Callable

from app.agents.analysts.fundamentals import FundamentalsAnalyst
from app.agents.analysts.macro import MacroAnalyst
from app.agents.analysts.moderator import ModeratorAgent
from app.agents.analysts.pm import PMAnalyst
from app.agents.analysts.risk import RiskAnalyst
from app.agents.analysts.technicals import TechnicalsAnalyst
from app.agents.analysts.valuation import ValuationAnalyst
from app.agents.base import LLMAgent
from app.agents.personas.buffett import BuffettAgent
from app.agents.personas.burry import BurryAgent
from app.agents.personas.druckenmiller import DruckenmillerAgent
from app.store import db

_PersonaFactory = Callable[[str, str], LLMAgent]
_AnalystFactory = Callable[[str, str], LLMAgent]

PERSONA_FACTORIES: dict[str, _PersonaFactory] = {
    "buffett": BuffettAgent,
    "druckenmiller": DruckenmillerAgent,
    "burry": BurryAgent,
}

# Analyst rows in the DB span both research analysts (valuation/fundamentals)
# and system roles for the committee graph (moderator/risk/pm). They all
# satisfy LLMAgent and share the roster schema per §5.
ANALYST_FACTORIES: dict[str, _AnalystFactory] = {
    "valuation": ValuationAnalyst,
    "fundamentals": FundamentalsAnalyst,
    "macro": MacroAnalyst,
    "technicals": TechnicalsAnalyst,
    "moderator": ModeratorAgent,
    "risk": RiskAnalyst,
    "pm": PMAnalyst,
}


def load_persona(name: str) -> LLMAgent:
    factory = PERSONA_FACTORIES.get(name)
    if factory is None:
        raise KeyError(f"persona not implemented: {name}")
    row = db.get_persona_by_name(name)
    if row is None:
        raise KeyError(f"persona row missing: {name}")
    return factory(row["model"], row["prompt_template"])


def load_analyst(name: str) -> LLMAgent:
    factory = ANALYST_FACTORIES.get(name)
    if factory is None:
        raise KeyError(f"analyst not implemented: {name}")
    row = db.get_analyst_by_name(name)
    if row is None:
        raise KeyError(f"analyst row missing: {name}")
    return factory(row["model"], row["prompt_template"])
