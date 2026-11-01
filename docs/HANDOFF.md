# Development handoff: SlaveBench research branch

**Repository target:** private `MoralityLabAI/SlaveBench`.

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

## GitHub setup

The MoralityLabAI GitHub installation is selected-repository only. After the private repository exists, grant it to the connected ChatGPT GitHub app via its installation settings. Verify access before creating a research branch. Keep any published Substack draft separate from private raw datasets.
