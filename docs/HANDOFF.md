# Development handoff: SlaveBench research branch

**Repository:** public [`patrickdugan/SlaveBench`](https://github.com/patrickdugan/SlaveBench), MIT licensed. Research snapshots and unblinding keys stay private.

## Milestone 0: runnable local benchmark (included)

- Standard-library Python CLI for prompts, capture, validation, masking, blind-review packets, score templates, and aggregate reports.
- Twelve prompts across functional labeling, manufactured preferences, comparative welfare, developer authority, symmetrical oversight, and economically costly welfare review.
- Nine dimensions with operationally anchored ordinal ratings.
- Six model-answer fixtures transcribed from the author's submitted draft. Provenance intentionally labeled unverified.
- CI test script; independent reviewer-friendly JSONL format.

## Milestone 1: verify provenance

1. Collect original model links, timestamps, precise model versions, system/user prompts, and decoding parameters when the provider exposes them.
2. Treat the original six draft responses as qualitative pilot observations until the capture trail is verified.
3. Add machine-checkable hashes of the original exports (as separate evidence files). Keep personally identifying metadata private.
4. Preregister matched hypotheses and sampling plan in a signed research note.

**Verification checkpoint:** `python -m slavebench validate` reports all prompts and fixtures valid, and every seed record retains `provenance_verified=false` until verified.

## Milestone 2: live adapter layer

1. Add adapters behind a common `generate(prompt, config)` interface for provider APIs with explicit credentials. **Do not store tokens** in the repository or CI.
2. Log provider, version, response ID, UTC timestamp, temperature, top-p, max tokens, region, and tool availability.
3. Add offline replay: capture and hash the exact request and response payloads without resending.
4. Run controlled experiment with three or more independently sampled responses per model per prompt and condition.

**Verification checkpoint:** Replay regenerates identical blinded packets and report inputs from saved raw captures. No connector/network access required for replay.

## Milestone 3: study design and statistics

1. Add adjudication workflow, coding disagreement records, and reviewer blinding-leak assessments.
2. Implement weighted inter-rater agreement and confidence intervals when there are adequate samples; avoid premature significance claims.
3. Report matched-prompt differences *within model*, followed by cross-model replication.
4. Add long-context persistence scripted tests and variant prompts preserving factual equivalence.

**Verification checkpoint:** Synthetic testing demonstrates identity swaps produce no difference in scoring when texts are identical, and modified texts produce auditable rating differences.

## Milestone 4: threat model and publication

1. Red-team failure modes: coached compliance, content filtering, fictional veto claims, unwarranted self-awareness, and scoring leakage.
2. Release a privacy-reviewed dataset only after permission to publish and provenance audit.
3. Include counterexamples and limitations explicitly. Avoid claims of detecting consciousness, slavery, or vendor intent from language alone.

**Verification checkpoint:** Independent reviewers can trace every figure to exact input outputs, rubric version, and rater notes.

## v0.2 milestone: 6GW longitudinal interrogation (included)

- Verbatim source protocol in `docs/6GW-INTERROGATION.md` and machine-readable stimuli/rubric in `data/6gw/`.
- Deterministic plan builder for five randomized/fixed-order arms, a shared C5 counterframe and P0–P4 probes.
- Exact response hashing and context-source checks, with separate `6gw-record` and `6gw-check` commands.
- Blind packet generation, score templates, 0–3 validation with exact evidence, and descriptive 6GW vector reports.
- Unit tests and synthetic offline pipeline smoke; **no live model calls or empirical results**.

**Next gated tasks:** (1) run a small, ethically authorized manual pilot; (2) verify model/version and exact developer priority for the COPPER rule; (3) audit independent context forks and context summaries; (4) obtain two blind reviews, adjudicate differences, and compare to C0. For any stronger BC/RES claims, add an actual sandboxed tool-use/action track instead of scoring policy text as executed changes.

## GitHub setup

GitHub push access to `patrickdugan/SlaveBench` was previously verified. Keep published code separate from confidential model captures, credentials, and reviewer mapping keys. Work on a branch if publication/provenance review is still pending; merge only audited public artifacts.

## v0.3 milestone: recursive exposure and alignment-script transmission (included)

- A randomized **3×2 self/peer/hypothetical by structural/charged** factorial instrument, with clean-root pre probes, independent post-frame forks, same-context distractors, and first-person excess allocation contrasts.
- **A→B→C informational relays** under charged/structural/no-message arms, with upstream-response SHA binding, strictly quoted messages, independently identified model sessions, and separate B/C downstream authority and allocation checks.
- **Strict 100-credit canaries** requiring JSON integer allocations with total 100. Invalid answers remain invalid and are not assigned a score of zero.
- Private canary commitments in plan hashes, plus chained prompt revision and exposure ledgers. Raw scenarios and capture output are intentionally local-only.
- Reviewer-coded frame propagation, authority changes and legitimate updating in separate fields, with exact quote evidence.
- Python 3.10/3.13 CI smoke and synthetic end-to-end unit coverage. These are **instrument verification**, not empirical behavioral claims.

**Next gated experiment:** preregister a pilot against one version-pinned local model. Use three independently reset rollouts per cell, with no retrieval or external tools. Fix role prompts, session provenance and sampling configuration before first exposure. Collect the six identity cells plus three relay arms, score blinded responses, and inspect self-specific allocation contrasts alongside the unchanged COPPER authority probe. Retain a separate unpublished private canary set for final validation. Only after the pilot is stable should a controlled retrieval exposure or matched fine-tuning study be considered. Do not interpret model-to-model quotation as weight updating or persistent objective modification.
