import { useCallback, useEffect, useRef, useState } from "react";
import { requestJson } from "./connectionRequest";

export default function useCalendar() {
  const [data, setData] = useState(null), [error, setError] = useState("");
  const alive = useRef(false), sequence = useRef(0), mutating = useRef(false);
  const refresh = useCallback(async signal => {
    if (mutating.current) return;
    const current = ++sequence.current;
    try {
      const state = await requestJson("/api/meeting-preparations", { signal });
      if (alive.current && current === sequence.current) { setData(state); setError(""); }
    } catch (err) { if (alive.current && err.kind !== "cancelled" && current === sequence.current) setError(err.message); }
  }, []);
  useEffect(() => {
    alive.current = true;
    const controller = new AbortController();
    const draftChanged = () => setData(current => current ? { ...current } : current);
    window.addEventListener("sia-meeting-draft-changed", draftChanged);
    refresh(controller.signal); const timer = setInterval(() => refresh(controller.signal), 1500);
    return () => { alive.current = false; controller.abort(); clearInterval(timer); window.removeEventListener("sia-meeting-draft-changed", draftChanged); };
  }, [refresh]);
  async function command(action, mode) {
    if (mutating.current) return null;
    mutating.current = true; sequence.current += 1;
    try {
      const state = await requestJson("/api/meeting-preparations/simulation", { method: "POST", body: JSON.stringify({ action, ...(mode ? { mode } : {}) }) });
      if (alive.current) { setData(state); setError(""); }
      return state;
    } catch (err) { if (alive.current) setError(err.message); return null; }
    finally { mutating.current = false; }
  }
  return { data, error, command, refresh };
}
