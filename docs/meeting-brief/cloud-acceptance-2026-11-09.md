# Firestore and Gemini acceptance — 2026-11-09

After explicit authorization to use the selected household's cloud context with
Google Gemini, acceptance exercised the current branch against shared Firestore.
Only labeled DEBUG meetings were created, edited and deleted. Existing meetings
were not edited. Raw cloud records, credentials and screenshots are not committed.

## Confirmed failures and repairs

The first attempt saved its meeting but progress requests exceeded 30 seconds
during discovery. ADK's synchronous tool functions were performing cloud reads on
the event loop. A heartbeat regression reproduced the failure offline. The ADK
tool adapters now offload those reads while serializing shared checkpoint/trace
writes; this is nonblocking I/O, not parallel investigation. Backend-required
coverage reads also run outside the event loop.

Repeated store construction caused repeated Application Default Credentials
discovery, which invoked gcloud while gRPC threads were active. Store adapters now
reuse one Firestore client per project. Concurrent initialization is protected,
and different projects retain separate clients. This changes connection management,
not the A/C agent logic or model selection. CRM settings, context and source reads
are frozen within one preparation and refreshed for the next preparation.

Calendar validation also read cloud records synchronously. Create/update validation
now runs in a worker thread. Save requests have a bounded 30-second timeout and a
message explaining that a timed-out save may already have completed. The editor's
Save & view prep action waits for persistence, then fetches the current normalized
appointment before navigation.

## Live result

The initial interrupted preparation resumed its checkpoint with seven completed
reads. The completed initial brief had six sections, valid references, and a pass
from the independent semantic reviewer using gemini-3.5-flash-lite.

The acceptance script initially checked persisted Notes immediately after a browser
click, before the save response completed. Its wait condition was corrected. The
same DEBUG fixture was restored with its original identity and content to reuse
the exact completed first brief; no third full preparation was generated.

Saving revised Notes then produced a new event version, a different brief ID and
a second independently checked pass. The discussion priorities changed with the
new meeting scope. The updated preparation completed in approximately 15 seconds.
There are exactly two completed model preparation runs in the isolated debug store.

All three exact DEBUG titles from the attempted runs were checked for cleanup;
none remained in shared Firestore. Brief snapshots and checkpoints remain only
in the local debug SQLite database for review. Automatic scanning remains paused.

## Verification

- 84 related offline tests and 24 subtests passed.
- Real browser flow verified Firestore create/update/delete, current-version
  navigation, initial Gemini output and Notes-triggered regeneration.
- Both completed live briefs passed objective checks and independent semantic
  review, with six sections and valid source references.
- UI screenshots and the detailed acceptance report are local artifacts under
  `/private/tmp/sia-live-cloud-tests/`.

This validates one selected household and this local runtime. It does not establish
production availability or model behavior for every household.
