"""Central config. Model IDs, pricing, budgets, paths. See CLAUDE.md §8 and §9."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

# CLAUDE.md §8 — model IDs. Personas.model is the source of truth; these are
# the canonical values a persona row may hold.
ModelId = Literal[
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
]

# CLAUDE.md §9 — pricing table (USD per 1M tokens). Used for in-process cost
# tracking. Update alongside Anthropic's published prices.
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-7": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}


# Firm-level chrome that wraps every memo. Tweak via env or by editing this
# file. CLAUDE.md §14 — this is an educational tool; the disclaimer below
# is load-bearing and must stay attached to every artifact.
FIRM_NAME = "manage"
ANALYST_EMAIL_DOMAIN = "manage.ai"

COMPLIANCE_FOOTER_MD = (
    "---\n\n"
    "**Important disclosures.** This memo was produced by AI personas as an\n"
    "educational and analytical exercise. It is **not investment advice**, an\n"
    "offer, or a solicitation. The author personas paraphrase the public\n"
    "investing styles of the named investors; they are not the real people\n"
    "and quotes are not theirs. Numbers come from market-data feeds and may\n"
    "be stale. Models are imperfect; outputs may contain mistakes. Do your\n"
    "own work before acting on anything here.\n"
)

# Display metadata for byline cards.
PERSONA_BYLINES: dict[str, dict[str, str]] = {
    "buffett": {
        "name": "Buffett desk",
        "role": "Long-horizon value",
        "email": f"buffett@{ANALYST_EMAIL_DOMAIN}",
    },
    "druckenmiller": {
        "name": "Druckenmiller desk",
        "role": "Macro / momentum",
        "email": f"druckenmiller@{ANALYST_EMAIL_DOMAIN}",
    },
    "burry": {
        "name": "Burry desk",
        "role": "Contrarian / balance sheet",
        "email": f"burry@{ANALYST_EMAIL_DOMAIN}",
    },
}

ANALYST_BYLINES: dict[str, dict[str, str]] = {
    "valuation": {"name": "Valuation desk", "email": f"valuation@{ANALYST_EMAIL_DOMAIN}"},
    "fundamentals": {
        "name": "Fundamentals desk",
        "email": f"fundamentals@{ANALYST_EMAIL_DOMAIN}",
    },
    "macro": {"name": "Macro desk", "email": f"macro@{ANALYST_EMAIL_DOMAIN}"},
    "technicals": {
        "name": "Technicals desk",
        "email": f"technicals@{ANALYST_EMAIL_DOMAIN}",
    },
    "risk": {"name": "Risk desk", "email": f"risk@{ANALYST_EMAIL_DOMAIN}"},
    "pm": {"name": "Portfolio manager", "email": f"pm@{ANALYST_EMAIL_DOMAIN}"},
    "moderator": {"name": "Moderator", "email": f"moderator@{ANALYST_EMAIL_DOMAIN}"},
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING.get(model)
    if p is None:
        return 0.0
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    financial_datasets_api_key: str = Field(default="", alias="FINANCIAL_DATASETS_API_KEY")

    daily_budget_usd: float = Field(default=5.00, alias="DAILY_BUDGET_USD")
    default_job_budget_usd: float = Field(default=0.50, alias="DEFAULT_JOB_BUDGET_USD")

    backend_host: str = Field(default="127.0.0.1", alias="BACKEND_HOST")
    backend_port: int = Field(default=8787, alias="BACKEND_PORT")

    database_path: str = Field(default="data/fund.sqlite", alias="DATABASE_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def database_file(self) -> Path:
        p = Path(self.database_path)
        return p if p.is_absolute() else REPO_ROOT / p


settings = Settings()
