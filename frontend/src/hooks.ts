import { useEffect, useState } from "react";
import { getState, PluginState } from "./api";

// Polls backend state while the panel is mounted. Decky's bridge is
// request/response only (no push channel to a mounted panel), so the panel
// refreshes on an interval; the backend remains authoritative. On failure the
// last known state is kept rather than showing a fabricated one.
export function usePluginState(intervalMs = 500): PluginState | null {
  const [state, setState] = useState<PluginState | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const s = await getState();
        if (!cancelled) setState(s);
      } catch {
        // backend unreachable; keep last known state
      }
    };
    void tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  return state;
}
