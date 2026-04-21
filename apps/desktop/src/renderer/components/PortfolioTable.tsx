import { useState } from "react";
import type { PortfolioPosition } from "../types.js";

interface Props {
  positions: PortfolioPosition[];
  onChange(): void;
}

export function PortfolioTable({ positions, onChange }: Props): JSX.Element {
  const [ticker, setTicker] = useState("");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    const cleanTicker = ticker.trim().toUpperCase();
    const qNum = parseFloat(qty);
    const pNum = parseFloat(price);
    if (!cleanTicker || Number.isNaN(qNum) || Number.isNaN(pNum)) {
      setError("ticker, qty, and avg price are all required");
      return;
    }
    setBusy(true);
    try {
      await window.api.upsertPosition({
        ticker: cleanTicker,
        qty: qNum,
        avg_price: pNum,
      });
      setTicker("");
      setQty("");
      setPrice("");
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number): Promise<void> {
    try {
      await window.api.deletePosition(id);
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const notional = positions.reduce((sum, p) => sum + p.qty * p.avg_price, 0);

  return (
    <div className="border border-neutral-800 rounded bg-neutral-950/60 overflow-hidden">
      <header className="flex justify-between items-baseline px-4 py-3 border-b border-neutral-800">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Portfolio</h3>
          <div className="text-xs text-neutral-500">
            Notional (at avg cost): ${notional.toLocaleString(undefined, {
              maximumFractionDigits: 2,
            })}
          </div>
        </div>
      </header>

      {positions.length === 0 ? (
        <div className="px-4 py-4 text-xs text-neutral-600">
          No positions yet.
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-xs text-neutral-500">
            <tr className="border-b border-neutral-800">
              <th className="text-left px-4 py-2">Ticker</th>
              <th className="text-right px-4 py-2">Qty</th>
              <th className="text-right px-4 py-2">Avg price</th>
              <th className="text-right px-4 py-2">Cost basis</th>
              <th />
            </tr>
          </thead>
          <tbody className="font-mono">
            {positions.map((p) => (
              <tr key={p.id} className="border-b border-neutral-900">
                <td className="px-4 py-2">{p.ticker}</td>
                <td className="text-right px-4 py-2">{p.qty}</td>
                <td className="text-right px-4 py-2">
                  ${p.avg_price.toFixed(2)}
                </td>
                <td className="text-right px-4 py-2">
                  ${(p.qty * p.avg_price).toLocaleString(undefined, {
                    maximumFractionDigits: 2,
                  })}
                </td>
                <td className="text-right px-4 py-2">
                  <button
                    type="button"
                    onClick={() => void remove(p.id)}
                    className="text-xs text-rose-400 hover:text-rose-300"
                  >
                    remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <form
        onSubmit={submit}
        className="flex items-end gap-2 px-4 py-3 border-t border-neutral-800"
      >
        <div className="flex-1">
          <label className="text-xs text-neutral-500 block mb-1">Ticker</label>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="NVDA"
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-2 py-1.5 font-mono uppercase text-sm"
          />
        </div>
        <div className="w-24">
          <label className="text-xs text-neutral-500 block mb-1">Qty</label>
          <input
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-2 py-1.5 font-mono text-sm"
          />
        </div>
        <div className="w-32">
          <label className="text-xs text-neutral-500 block mb-1">
            Avg price
          </label>
          <input
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-2 py-1.5 font-mono text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="px-3 py-1.5 rounded bg-neutral-800 border border-neutral-700 text-sm disabled:opacity-40"
        >
          Add / update
        </button>
      </form>
      {error && (
        <div className="px-4 pb-3 text-xs text-rose-400">{error}</div>
      )}
    </div>
  );
}
