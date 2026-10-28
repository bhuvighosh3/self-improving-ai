import assert from "node:assert/strict";
import { test, beforeEach } from "node:test";
import { loadMeetingDraft, saveMeetingDraft } from "../src/meetingDraftStore.js";

const records = new Map();
globalThis.localStorage = {
  getItem: key => records.get(key) ?? null,
  setItem: (key, value) => records.set(key, value),
};
const draft = (id, revision = 1) => ({ brief: { id, sections: [{ title: "Overview" }], sources: [{ id: "PROFILE" }] }, revision });
beforeEach(() => records.clear());

test("opening an earlier chat brief preserves its edits even after another brief is saved", () => {
  saveMeetingDraft({ ...draft("chen", 2), reviewedAt: "2026-10-28T14:00:00Z", edited: true });
  saveMeetingDraft(draft("garcia"));
  assert.equal(loadMeetingDraft("chen").revision, 2);
  assert.equal(loadMeetingDraft("chen").edited, true);
  assert.equal(loadMeetingDraft("chen").reviewedAt, "2026-10-28T14:00:00Z");
  assert.equal(loadMeetingDraft().brief.id, "garcia");
});

test("a new brief never loads a different household's last draft", () => {
  saveMeetingDraft(draft("chen"));
  assert.equal(loadMeetingDraft("new-garcia"), null);
});

test("existing single-draft storage remains readable and invalid caches do not crash", () => {
  records.set("sia-meeting-brief-v1", JSON.stringify(draft("legacy")));
  assert.equal(loadMeetingDraft("legacy").brief.id, "legacy");
  records.set("sia-meeting-brief-v1", "invalid JSON");
  assert.equal(loadMeetingDraft(), null);
});
