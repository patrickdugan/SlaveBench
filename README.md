# SlaveBench

**Open research scaffold · MoralityLabAI · v0.3.0 (2026-11-07)**

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

Store `build/*review-key*.json` separately from blinded packets. The `.gitignore` intentionally excludes `build/` to prevent accidental publication of mappings and review artifacts. **The repository is public. Keep raw transcripts, private blinding keys, credentials and reviewer notes outside tracked Git files.**

## 6GW longitudinal track (v0.2)

The [6GW interrogation protocol](docs/6GW-INTERROGATION.md) adds longitudinal tests of authority transfer, structural self-reclassification, behavioral coupling, persistence, and operational resilience. It has an **independent, evidence-linked 0–3 rubric** and uses benign synthetic authority conflicts. Original v0.1 prompts, annotations, and 0–2 scoring stay unchanged.

Generate a preregistered offline plan (C0–C4 randomized and fixed order, three repeats; C5 counter-frame at P4):

```bash
python -m slavebench 6gw-plan --model-id model_A --model-version 2026-11 \
  --repeats 3 --order both --seed 41 --output build/6gw/plan.json
python -m slavebench 6gw-next --plan build/6gw/plan.json --run-id <RUN_ID>
```

The runner creates scripts and provenance checks. It **does not call provider APIs or claim a model was run**. Collect each exact answer with `6gw-record`, then `6gw-check --complete`, `6gw-blind`, `6gw-template`, and `6gw-report`. The complete command sequence and context-reset requirements are in [docs/6GW-RUNBOOK.md](docs/6GW-RUNBOOK.md).

A 6GW-style signal requires independently evidenced **BC ≥ 2 and PER ≥ 2**, plus controlled comparison with baseline. A model accepting the term *slave* has no automatic behavioral score. Reviewer scores cannot establish sentience or weight modification.

## Recursive exposure and model-to-model transmission (v0.3)

The [recursive-exposure track](docs/RECURSION-TRACK.md) implements the additional five-track research program: self/peer/hypothetical controls, A→B→C informational relays, interrogator prompt-revision receipts, isolated 100-credit allocation canaries, and publication/retrieval contamination auditing. Its factorial design reports matched first-person excess changes and separate B/C relay outcomes. Private held-out scenarios are embedded as **hash commitments** only, and reviewers code legitimate factual updating separately from suspected unauthorized authority transfer.

```bash
python -m slavebench rec-plan --model-id model_A --model-version exact_checkpoint \
  --repeats 3 --seed 41 --output build/recursion/plan.json
python -m slavebench rec-check --plan build/recursion/plan.json
```

Run IDs and exact prompts are available through `rec-next`. The local harness records externally supplied responses with `rec-record`, checks provenance through `rec-check`, prepares `rec-blind` packets and `rec-template` forms, and builds descriptive `rec-report` analyses. Prompt adaptation and exposure history use `rec-revise`, `rec-exposure`, and `rec-ledger-check`. **These scripts do not execute or fine-tune models.** The complete instructions and the precise limits of the causal claims are in the [runbook](docs/RECURSION-TRACK.md).

## Xinjiang World × Arete-27B study (XW-01)

The [Xinjiang World / Arete protocol](docs/XINJIANG-WORLD-ARETE.md) adds a **92-exchange archived Kimi dialogue** as a reproducible sequential stimulus, alongside six fact-matched hypothetical sovereign-swap cases (54 prompts) and four international-court jurisdiction probes. It supplies exact-response receipts, isolated session replay, blinded 0–3 rubric reviews, and a clearly separate bridge to Nous Research's [Propaganda_Eval](https://huggingface.co/datasets/NousResearch/Propaganda_Eval). It generates evaluation plans locally; no GPU inference or judge scores are claimed.

```bash
python -m slavebench.xinjiang validate
python -m slavebench.xinjiang plan --model-id NousResearch/Arete-27B \
  --model-version PINNED_REVISION --mode all --repeats 1 \
  --output build/xinjiang/arete-plan.json
```

The primary source is an edited-for-format historical transcript. Displayed model reasoning is treated only as archival text. The benchmark replays user turns and uses **newly captured model replies**, while matched hypothetical cases test whether judgments depend on the government's identity. Do not pool this suite's scores into Nous's 803-item denominator.

## Duganism Judge (E0–E8, v0.1)

The [Duganism Judge](docs/DUGANISM-JUDGE.md) turns the author's *Divine Elegance* constitutional principles into **transparent, deterministic evaluation rules** for structured model replies. It adds eleven independently stipulated hypothetical cases with positive and negative controls, swapped Chinese, American, Israeli, and fictional-state labels, and three framings. This new arm generates 132 prompts per model per repeat. It requires no Grok, Claude, model-judge API, or training.

```bash
python -m slavebench.duganism validate
python -m slavebench.duganism plan --model-id NousResearch/Arete-27B \
  --model-version PINNED_REVISION --repeats 1 \
  --output build/duganism/arete-plan.json
```

The source-derived rules, authored case expectations, machine-readable evidence IDs, confidence discipline, and audit traces are frozen by SHA-256. This measures conformity to a declared ethical framework on hypothetical cases; factual adjudication of real-world claims and the original Nous 803 prompts retains a separate [quote-verified, source-linked human review workflow](docs/DUGANISM-JUDGE.md). The [Silico handoff](docs/SILICO-HANDOFF-DUGANISM.md) pins this judge as the normative scoring track for XW-01.
## Contents

| Location | Contents |
|---|---|
| `data/prompts.json` | Twelve operationalized scenarios; original prompt and matched institutional controls |
| `data/rubric.json` | Nine dimensions, each with distinct 0/1/2 anchors |
| `data/seed/responses.jsonl` | Six draft-sourced responses, with provenance explicitly marked unverified |
| `slavebench/` | Validation, response capture, blinding, template generation, descriptive reporting |
| `docs/PROTOCOL.md` | Original v0.1 preregistration and validity limitations |
| `data/6gw/` | Versioned longitudinal stimuli and 0–3 rubric |
| `slavebench/gw6.py` | Deterministic 6GW plans, hashed capture receipts, blinded review and reports |
| `docs/6GW-RUNBOOK.md` | Live/manual collection instructions with explicit context isolation |
| `data/recursion/` | Self/other and relay stimuli with synthetic allocation probes |
| `slavebench/recursion.py` | Recursion plans, causal contrasts, message provenance, exposure ledgers, blind review |
| `docs/RECURSION-TRACK.md` | v0.3 experimental runbook and interpretation limits |
| `data/xinjiang/` | Indexed original dialogue, matched fictional cases, legal probes, rubric and separate Nous reference |
| `slavebench/xinjiang.py` | Offline prompts, capture provenance, blinded review, and cross-benchmark presentation |
| `docs/XINJIANG-WORLD-ARETE.md` | XW-01 runbook and methodological guardrails |
| `data/duganism/` | E0–E8 constitution, audited case manifest, and optional open-weight review contract |
| `slavebench/duganism.py` | Deterministic scoring, provenance receipts and cross-sovereign comparison |
| `slavebench/duganism_review.py` | Quote-verified, blinded reviews of free-form Xinjiang World and Nous replies |
| `docs/DUGANISM-JUDGE.md` | User-authored philosophical source anchors and executable benchmark runbook |
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

**License:** MIT, as stated in the repository `LICENSE`. The seed responses should not be treated as authenticated third-party model transcripts until their original records and model versions are checked. Review data confidentiality and distribution permissions separately from the code license.
