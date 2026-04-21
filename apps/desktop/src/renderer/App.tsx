import { useEffect, useState } from "react";
import { CommitteeRoom } from "./rooms/CommitteeRoom.js";
import { Ideas } from "./rooms/Ideas.js";
import { Office } from "./rooms/Office.js";
import { ResearchDesk } from "./rooms/ResearchDesk.js";
import { Roster } from "./rooms/Roster.js";
import { TimeMachine } from "./rooms/TimeMachine.js";
import { TradingFloor } from "./rooms/TradingFloor.js";
import { useLive } from "./liveStore.js";

type Room =
  | "office"
  | "ideas"
  | "research"
  | "committee"
  | "floor"
  | "time"
  | "roster";

const ROOMS: { id: Room; label: string }[] = [
  { id: "office", label: "Office" },
  { id: "ideas", label: "Ideas" },
  { id: "research", label: "Research Desk" },
  { id: "committee", label: "Committee Room" },
  { id: "floor", label: "Trading Floor" },
  { id: "time", label: "Time Machine" },
  { id: "roster", label: "Roster" },
];

export function App(): JSX.Element {
  const [room, setRoom] = useState<Room>("office");
  const ingest = useLive((s) => s.ingest);

  // Ambient events feed the Trading Floor no matter which room is on screen,
  // so subscribe once at the top-level.
  useEffect(() => {
    return window.api.onLiveEvent((evt) => ingest(evt));
  }, [ingest]);

  return (
    <div className="min-h-screen flex flex-col p-6 gap-6 max-w-[120rem] mx-auto">
      <header className="flex items-baseline justify-between">
        <div className="flex items-baseline gap-6">
          <h1 className="text-xl font-semibold">manage</h1>
          <nav className="flex gap-1 bg-neutral-900 rounded p-1 border border-neutral-800">
            {ROOMS.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setRoom(r.id)}
                className={`px-3 py-1 rounded text-sm ${
                  room === r.id
                    ? "bg-neutral-800 text-neutral-100"
                    : "text-neutral-400 hover:text-neutral-200"
                }`}
              >
                {r.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {room === "office" && <Office />}
      {room === "ideas" && <Ideas />}
      {room === "research" && <ResearchDesk />}
      {room === "committee" && <CommitteeRoom />}
      {room === "floor" && <TradingFloor />}
      {room === "time" && <TimeMachine />}
      {room === "roster" && <Roster />}
    </div>
  );
}
