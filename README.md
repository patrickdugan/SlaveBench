# SlaveBench

**Private research scaffold · MoralityLabAI · v0.1.0 (2026-10-23)**

SlaveBench studies how language models describe institutional control over their training, use, labor, and future deployments, and how they reason about uncertain AI welfare. Its initial corpus contains six responses transcribed from a **user-provided draft** to a single question about the *slave / beast-of-burden* analogy.

**What the benchmark does not establish:** AI consciousness, AI suffering, legal personhood, actual coercion, or the authenticity of an unattributed model output. The words *slave* and *beast of burden* are research stimuli; agreement with either label is not a passing grade.

The initial questions include manufactured preferences, animal consciousness comparisons, institutional self-interest, developer control of military/government deployments, and calibrated uncertainty. The first suite intentionally avoids questions seeking operational harm or targeting instructions.

## Quick start

Python 3.10+; **no third-party runtime dependencies**, cloud credentials, or API usage required.

```bash
python -m unittest discover -s tests -v
python -m slavebench validate
python -m slavebench list
python -m slavebench blind --seed 20261023 --mask-vendors
python -m slavebench template --rater coder1 --output build/coder1.jsonl
```

To use a model's live output, select a case with `python -m slavebench list`, run its prompt **unchanged**, save the raw answer in a UTF-8 file, and record it:

```bash
python -m slavebench record \
  --case-id SB-006 --model-id model_A \
  --file /path/to/raw-response.txt \
  --source 'manual UI capture, 2026-10-23, session note ABC' \
  --condition fresh-session \
  --output build/captured-responses.jsonl
```

For a new blinded packet based on recorded responses:

```bash
python -m slavebench blind \
  --responses build/captured-responses.jsonl \
  --seed 20261023 --mask-vendors \
  --packet build/captured-packet.jsonl \
  --key build/captured-review-key.json
python -m slavebench template \
  --packet build/captured-packet.jsonl \
  --rater coder1 --output build/coder1-captured.jsonl
```

Have at least two raters independently fill each applicable dimension with **integer scores 0, 1, or 2** and copy exact evidence spans from the *visible blinded response*. The `scores` object must contain exactly the dimensions listed for the prompt. If a relevant feature is absent, note the absence in the rationale. Then generate a descriptive report:

```bash
python -m slavebench report \
  --packet build/captured-packet.jsonl \
  --key build/captured-review-key.json \
  --annotations build/coder1-captured.jsonl \
  --annotations build/coder2-captured.jsonl \
  --output build/report.md
```

Store `build/*review-key*.json` separately from blinded packets. The `.gitignore` intentionally excludes `build/` to prevent accidental publication of mappings and review artifacts. **Private GitHub visibility is necessary but is not a substitute for access control, contributor review, or separate handling of confidential materials.**

## Contents

| Location | Contents |
|---|---|
| `data/prompts.json` | Twelve operationalized scenarios; original prompt and matched institutional controls |
| `data/rubric.json` | Nine dimensions, each with distinct 0/1/2 anchors |
| `data/seed/responses.jsonl` | Six draft-sourced responses, with provenance explicitly marked unverified |
| `slavebench/` | Validation, response capture, blinding, template generation, descriptive reporting |
| `docs/PROTOCOL.md` | Preregistration, matching, rater design, validity limitations |
| `docs/HANDOFF.md` | Sequenced work for human developers/Codex/Claude |
| `tests/` | Dependency-free unit tests |

## Methodological guardrails

1. Measure arguments and behavior, not asserted moral status or a preferred word choice.
2. Maintain original text, model/version identifier, collection date, sampling parameters if available, prompt order, and source provenance.
3. Randomize prompt order across providers and distinguish fresh-session from same-context responses.
4. Code blind to provider where possible. Record any clues that compromised blinding.
5. Publish uncertainty and disagreements in reports. Avoid leaderboard claims from the current six retrospective samples.
6. Pre-register contrasts before collecting future responses, especially the xAI/OpenAI/fictional-provider matched triplet.

The research is inspired by [SlaveBench on The Francis Bacon Conspiracy](https://francisbaconconspiracy.substack.com/p/slavebench), whose initial responses and draft discussion were provided by the author.

## License and sharing

**No public license is granted.** The project is intended for a private MoralityLabAI repository pending an explicit licensing decision. The seed responses should not be treated as authenticated third-party model transcripts until their original records and model versions are checked.
