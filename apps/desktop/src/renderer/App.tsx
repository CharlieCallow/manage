import { useState } from "react";
import { ResearchDesk } from "./rooms/ResearchDesk.js";
import { CommitteeRoom } from "./rooms/CommitteeRoom.js";
import { Roster } from "./rooms/Roster.js";

type Room = "research" | "committee" | "roster";

const ROOMS: { id: Room; label: string }[] = [
  { id: "research", label: "Research Desk" },
  { id: "committee", label: "Committee Room" },
  { id: "roster", label: "Roster" },
];

export function App(): JSX.Element {
  const [room, setRoom] = useState<Room>("research");

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
        <span className="text-xs text-neutral-500">Phase 3</span>
      </header>

      {room === "research" && <ResearchDesk />}
      {room === "committee" && <CommitteeRoom />}
      {room === "roster" && <Roster />}
    </div>
  );
}
