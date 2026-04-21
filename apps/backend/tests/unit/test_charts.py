"""Unit tests for app/tools/charts.py.

Doesn't render to screen — uses the Agg backend and only checks that we
get non-trivial PNG bytes out.
"""
from __future__ import annotations

import pytest

from app.tools import charts


def _snapshot_with_series(n: int) -> dict[str, object]:
    return {
        "ticker": "NVDA",
        "as_of": "2024-01-05",
        "weekly_closes_52w": [
            {"date": f"2024-{(i % 12) + 1:02d}-01", "close": 100.0 + i}
            for i in range(n)
        ],
    }


def test_render_price_chart_returns_png() -> None:
    data = charts.render_price_chart(_snapshot_with_series(52))
    assert data is not None
    # PNG magic number
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    # Not trivially small
    assert len(data) > 1_000


def test_render_price_chart_returns_none_without_series() -> None:
    assert charts.render_price_chart({"ticker": "NVDA"}) is None
    assert charts.render_price_chart({"weekly_closes_52w": []}) is None
    assert charts.render_price_chart({"weekly_closes_52w": [{"date": "x", "close": 1}]}) is None


def test_save_chart_png_rejects_unsafe_names() -> None:
    with pytest.raises(ValueError):
        charts.save_chart_png("job", "../oops", b"x")
    with pytest.raises(ValueError):
        charts.save_chart_png("job", "sub/dir", b"x")


def test_save_and_url(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Redirect the DB path so chart_dir_for lands in tmp.
    from app.config import settings

    monkeypatch.setattr(settings, "database_path", str(tmp_path / "fund.sqlite"))
    png = charts.render_price_chart(_snapshot_with_series(20))
    assert png is not None
    path = charts.save_chart_png("job-abc", "price", png)
    assert path.exists()
    assert charts.chart_url("job-abc", "price").endswith("/charts/job-abc/price.png")
