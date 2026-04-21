"""Server-side chart rendering.

Returns PNG bytes so the caller can persist under data/charts/{job_id}/... and
serve them via the /charts route. Uses the Agg backend so no display is
required. CLAUDE.md §4 — agents don't draw; they reference the URLs we
inject into the memo from the graph.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from app.config import REPO_ROOT, settings

logger = logging.getLogger(__name__)


# Dark-first palette to match the app's look.
_COLOR_BG = "#0a0a0a"
_COLOR_FG = "#e5e5e5"
_COLOR_GRID = "#262626"
_COLOR_PRICE = "#f59e0b"  # amber-500
_COLOR_MA50 = "#34d399"  # emerald-400
_COLOR_MA200 = "#60a5fa"  # blue-400


def _charts_root() -> Path:
    return settings.database_file.parent / "charts"


def chart_dir_for(job_id: str) -> Path:
    path = _charts_root() / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_price_chart(snapshot: dict[str, Any]) -> bytes | None:
    """Render a price + MA50 + MA200 chart from a snapshot. Returns None
    when the required series isn't available."""
    closes = snapshot.get("weekly_closes_52w") or []
    if len(closes) < 4:
        return None

    dates = [c.get("date") for c in closes if c.get("date")]
    prices = [c.get("close") for c in closes if c.get("close") is not None]
    if len(dates) != len(prices) or len(prices) < 4:
        return None

    ma50 = _rolling_mean(prices, 10)   # ~10 weeks ≈ 50 sessions
    ma200 = _rolling_mean(prices, 40)  # ~40 weeks ≈ 200 sessions

    fig, ax = plt.subplots(figsize=(8.0, 3.2), dpi=160)
    fig.patch.set_facecolor(_COLOR_BG)
    ax.set_facecolor(_COLOR_BG)

    ax.plot(dates, prices, color=_COLOR_PRICE, linewidth=1.8, label="Close (weekly)")
    ma50_plot = [float("nan") if v is None else v for v in ma50]
    ma200_plot = [float("nan") if v is None else v for v in ma200]
    if any(v is not None for v in ma50):
        ax.plot(dates, ma50_plot, color=_COLOR_MA50, linewidth=1.1, label="MA ~50d")
    if any(v is not None for v in ma200):
        ax.plot(dates, ma200_plot, color=_COLOR_MA200, linewidth=1.1, label="MA ~200d")

    ticker = str(snapshot.get("ticker", "")).upper()
    as_of = snapshot.get("as_of") or ""
    ax.set_title(
        f"{ticker} · 52w close" + (f" · as of {as_of}" if as_of else ""),
        color=_COLOR_FG,
        fontsize=11,
        loc="left",
    )

    ax.tick_params(colors=_COLOR_FG, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(_COLOR_GRID)
    ax.grid(True, color=_COLOR_GRID, linewidth=0.4)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"${v:,.0f}"))

    # Thin out the x-tick labels so they don't collide on weekly data.
    if len(dates) > 12:
        step = max(1, len(dates) // 12)
        for idx, label in enumerate(ax.get_xticklabels()):
            if idx % step != 0:
                label.set_visible(False)
    fig.autofmt_xdate()

    leg = ax.legend(
        loc="upper left",
        fontsize=8,
        facecolor=_COLOR_BG,
        edgecolor=_COLOR_GRID,
        labelcolor=_COLOR_FG,
    )
    if leg:
        leg.get_frame().set_linewidth(0.5)

    fig.tight_layout(pad=0.6)

    buf = io.BytesIO()
    try:
        fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    finally:
        plt.close(fig)
    return buf.getvalue()


def save_chart_png(job_id: str, name: str, data: bytes) -> Path:
    """Write a PNG to disk under data/charts/{job_id}/{name}.png."""
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError(f"unsafe chart filename: {name}")
    target_dir = chart_dir_for(job_id)
    target = target_dir / f"{name}.png"
    target.write_bytes(data)
    return target


def chart_url(job_id: str, name: str) -> str:
    """The URL the renderer should embed for an on-disk chart PNG."""
    host = settings.backend_host
    port = settings.backend_port
    return f"http://{host}:{port}/charts/{job_id}/{name}.png"


def _rolling_mean(values: list[float], window: int) -> list[float | None]:
    if window <= 0:
        return [None] * len(values)
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
            continue
        window_slice = values[i + 1 - window : i + 1]
        out.append(sum(window_slice) / window)
    return out


# REPO_ROOT import kept for callers that compose paths relative to the
# repo root (reserved for future multi-chart features).
_ = REPO_ROOT
