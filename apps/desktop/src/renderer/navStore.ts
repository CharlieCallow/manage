import { create } from "zustand";

export type Room =
  | "office"
  | "ideas"
  | "research"
  | "committee"
  | "floor"
  | "time"
  | "archive"
  | "roster";

interface NavState {
  room: Room;
  selectedJobId: string | null;
  goto(room: Room): void;
  openJob(jobId: string): void;
  clearSelection(): void;
}

export const useNav = create<NavState>((set) => ({
  room: "office",
  selectedJobId: null,
  goto(room) {
    set({ room });
  },
  openJob(jobId) {
    set({ room: "archive", selectedJobId: jobId });
  },
  clearSelection() {
    set({ selectedJobId: null });
  },
}));
