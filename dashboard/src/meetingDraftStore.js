const STORAGE_KEY = "sia-meeting-brief-v1";

export function loadMeetingDraft(briefId = null) {
  try {
    const keys = briefId ? [`${STORAGE_KEY}:${briefId}`, STORAGE_KEY] : [STORAGE_KEY];
    for (const key of keys) {
      const saved = JSON.parse(localStorage.getItem(key));
      if (saved?.brief?.sections?.length && saved.brief.sources?.length && (!briefId || saved.brief.id === briefId)) return saved;
    }
  } catch { /* A blocked or invalid browser cache must not block preparation. */ }
  return null;
}

export function saveMeetingDraft(draft) {
  try {
    localStorage.setItem(`${STORAGE_KEY}:${draft.brief.id}`, JSON.stringify(draft));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
    return true;
  } catch {
    return false;
  }
}
