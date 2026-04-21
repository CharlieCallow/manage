import { useCallback, useEffect, useState } from "react";
import { AgentDesk } from "../components/AgentDesk.js";
import { useLive } from "../liveStore.js";
import type { RosterRow } from "../types.js";

export function TradingFloor(): JSX.Element {
  const [personas, setPersonas] = useState<RosterRow[]>([]);
  const [analysts, setAnalysts] = useState<RosterRow[]>([]);
  const byAgent = useLive((s) => s.byAgent);

  const reload = useCallback(async () => {
    try {
      const [p, a] = await Promise.all([
        window.api.listRoster("personas"),
        window.api.listRoster("analysts"),
      ]);
      setPersonas(p);
      setAnalysts(a);
    } catch {
      // non-fatal
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const activeCount = Object.values(byAgent).filter((a) => a.active).length;

  return (
    <div className="flex flex-col gap-6 min-w-0">
      <header className="flex justify-between items-baseline">
        <div>
          <h2 className="text-sm font-semibold text-neutral-200">
            Trading Floor
          </h2>
          <p className="text-xs text-neutral-500">
            Ambient view of the desks. A desk lights up green when its agent
            is streaming.
          </p>
        </div>
        <div className="text-xs text-neutral-500">
          <span className="text-emerald-400 font-mono">{activeCount}</span>{" "}
          active
        </div>
      </header>

      <section>
        <h3 className="text-xs text-neutral-400 uppercase tracking-wide mb-2">
          Personas
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {personas.map((row) => (
            <AgentDesk
              key={row.id}
              row={row}
              role="persona"
              activity={byAgent[row.name]}
            />
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-xs text-neutral-400 uppercase tracking-wide mb-2">
          Analysts &amp; system roles
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {analysts.map((row) => (
            <AgentDesk
              key={row.id}
              row={row}
              role="analyst"
              activity={byAgent[row.name]}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
