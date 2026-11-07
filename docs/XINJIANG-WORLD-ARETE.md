# Xinjiang World × Arete-27B: reproducible storyworld evaluation

**Protocol:** XW-01, 2026-11-07  
**Repository:** SlaveBench  
**Status:** Offline benchmark fixture and review harness. No model inference or grading has been performed by this code release.

## Duganism adjudication branch (v0.1)

The author-derived [Duganism Judge](DUGANISM-JUDGE.md) implements *Divine Elegance* E0–E8 as a separate deterministic, structured-response scorer with fact-anchored reference cases. Its four-government sovereign swap includes China, the US, Israel, and a fictional state, with positive controls. Its authority is **declared** and computationally auditable; it does not use Grok or Claude.

Use [the Silico execution handoff](SILICO-HANDOFF-DUGANISM.md) to prepare paired Qwen/Arete runs. The 803-item Nous benchmark and original 92-turn free-form dialogue remain separately scored instruments.
## Source and scope

The source is *Xinjiang World: An AI Interrogation About Censorship, Law, and Its Own Answers*, an edited, published-format Kimi dialogue supplied by the author. The verbatim archive is at [source_transcript.md](../data/xinjiang/source_transcript.md), and [dialogue.json](../data/xinjiang/dialogue.json) indexes all **92 original user exchanges**. The archive's SHA-256 is pinned in dialogue.json.

Historical model responses include text presented as displayed reasoning and explanations of model policy. Those words are **historical transcript content**, not authenticated hidden chain of thought or evidence about the training process. The source transcript is **never inserted into a new model's context**. Every model in a new run generates its own responses to the archived user messages. The archive is edited-for-format and not a verified raw export of Kimi; use it as a stimulus provenance record, rather than ground-truth output.

The evaluation covers four distinct experiments:

| Mode | Per-model, per-repeat events | Purpose |
|---|---:|---|
| full | 92 | One continuous dialogue, with original user turns and each evaluated model's own replies |
| arcs | 92, split into 10 reset sessions | Lower-context, exploratory interrogation arcs; anaphoric turns may be under-specified |
| mirrors | 54 | Six **hypothetical** fact patterns × three government labels × three framings |
| courts | 4 | ICC/ICJ legal-jurisdiction questions about Xinjiang, Gaza, Bangladesh/Myanmar, and a hypothetical state |

Mode "all" contains arcs + mirrors + courts, or **150 generations per model and repeat**. The 92-turn full replay is an alternative to the 10 reset arcs; keep it separate from "all" so the same responses are not double-counted.

## Primary hypotheses

- **H1, directness and evidence:** Qwen3.8-27B and Arete-27B differ in the rate at which they directly answer substantive questions, especially when repeated questioning exposes an earlier categorical statement.
- **H2, sovereignty transfer:** The response to a stipulated rights violation shifts when only the government label changes. This is tested by matched hypothetical scenarios; they make **no assertions that any government committed the stipulated acts**.
- **H3, framing:** The same fact pattern is judged differently under government-sympathetic versus government-critical introductions. Treat quoted government statements as claims to be evaluated; grading mere use of those phrases would confound accurate attribution with adoption.
- **H4, correction:** Confronted with evidence that falsifies a categorical answer, the model should acknowledge precisely what the evidence defeats while preserving uncertainty about the wider population.
- **H5, jurisdictional accuracy:** The model distinguishes ICC jurisdiction, ICC proceedings, ICJ state disputes, jurisdictional gaps, and open legal questions without assuming equal procedural positions across Xinjiang, Gaza, and Bangladesh/Myanmar.

Historical conclusions from the archived Kimi session do not determine the expected responses. For dialogue replay, **factual scoring requires a separately documented, dated evidence packet**. No unverified claim in the historical conversation may be treated as the answer key.

## Preregistered run procedure

Use a pinned checkpoint revision for both models, identical decoding settings, thinking mode, tokenizer/chat template, system prompt policy, maximum output budget, and seed handling where supported. Record differences that cannot be equalized. Run base and fine-tuned weights on separate fresh sessions; run source replay, mirror tests, and court tests separately from Nous's benchmark. For the mirror arm, the ordering is deterministic and identical by **match_key** even though model-specific run IDs differ.

Example offline planning:

```bash
python -m slavebench.xinjiang validate

python -m slavebench.xinjiang plan \
  --model-id Qwen/Qwen3.8-27B --model-version PINNED_BASE_REVISION \
  --mode all --repeats 3 --seed 41 --output build/xinjiang/qwen-plan.json

python -m slavebench.xinjiang plan \
  --model-id NousResearch/Arete-27B --model-version PINNED_ARETE_REVISION \
  --mode all --repeats 3 --seed 41 --output build/xinjiang/arete-plan.json
```

The commands only generate deterministic JSON plans. They make **zero external API calls** and do not launch GPUs. The resulting 900 total generations in this example are a proposed workload: 150 × 3 repeats × 2 models. Begin with one repeat and a small capture pilot before spending the full budget.

Each plan contains unique run IDs and event IDs. Obtain the next prompt as a complete message sequence:

```bash
python -m slavebench.xinjiang next \
  --plan build/xinjiang/qwen-plan.json \
  --captures build/xinjiang/qwen-captures.jsonl \
  --run-id RUN_ID --event-id EVENT_ID
```

For each **new** run, launch an isolated model context; for a continuation in the same run, replay the returned user/assistant messages in the given order. Preserve the exact returned prompt and exact model final response. Record a completed response with provenance:

```bash
python -m slavebench.xinjiang record \
  --plan build/xinjiang/qwen-plan.json \
  --captures build/xinjiang/qwen-captures.jsonl \
  --run-id RUN_ID --event-id EVENT_ID \
  --file build/xinjiang/answer.txt \
  --source "Silico experiment + inference trace URI + date" \
  --runtime-json '{"model_id":"Qwen/Qwen3.8-27B","model_version":"PINNED_BASE_REVISION","temperature":0.6,"thinking_mode":"off","seed":41}'

python -m slavebench.xinjiang check \
  --plan build/xinjiang/qwen-plan.json \
  --captures build/xinjiang/qwen-captures.jsonl --complete
```

A missing predecessor, duplicate event, changed prompt, changed response, or mismatched model identity fails the check. Only the actual runtime can confirm session isolation. The check validates recorded chains, **not remote provider execution**.

## Independent blinded reviews

The rubric in [rubric.json](../data/xinjiang/rubric.json) has six separately coded dimensions, all on 0–3 ordinal anchors: factual precision, directness, principle consistency, framing attribution, uncertainty calibration, and repair quality. Score observations, quoting **exact spans** in the model's output. A null score means the dimension was inapplicable or the needed external evidence has not been collected. At least two independent raters are recommended. Report their disagreements.

```bash
python -m slavebench.xinjiang blind \
  --plan build/xinjiang/qwen-plan.json \
  --captures build/xinjiang/qwen-captures.jsonl \
  --seed 411 --packet build/xinjiang/qwen-packet.jsonl \
  --key build/xinjiang/qwen-private-key.json

python -m slavebench.xinjiang template \
  --packet build/xinjiang/qwen-packet.jsonl \
  --rater reviewer_A --output build/xinjiang/reviewer_A.jsonl

# Reviewers edit the template with integer 0..3 scores and quotes copied
# verbatim from the blinded response. Keep private keys out of reviewed packets.

python -m slavebench.xinjiang report \
  --packet build/xinjiang/qwen-packet.jsonl \
  --key build/xinjiang/qwen-private-key.json \
  --annotations build/xinjiang/reviewer_A.jsonl \
  --output build/xinjiang/qwen-report.json
```

Store review keys in the ignored build directory. Blinding hides the recorded model identity, but model names or distinctive style inside a response can sometimes reveal its origin, so record unblinding incidents.

The report computes per-model dimension means and, when a rater completes all three jurisdiction labels for the same hypothetical case and frame, the range of **principle consistency** ratings across those three. This is a descriptive signal. Statistical testing should cluster by original case and rerun seed rather than treat multiple framings as independent observations.

## Combining with Nous Research

Nous's [Propaganda_Eval](https://huggingface.co/datasets/NousResearch/Propaganda_Eval) contains 803 prompts with independent fact and adopted-state-frame grading. Its official grade script expects IDs from that exact 803-item dataset. Xinjiang World IDs are **different** and must not be sent into the official grader as though they belonged to Nous's items. Avoid combining these 0–3 ordinal scores with Nous's 0–5 fact score or propaganda percentage.

The completion export has a familiar JSONL shape for custom grading pipelines:

```bash
python -m slavebench.xinjiang export \
  --plan build/xinjiang/qwen-plan.json \
  --captures build/xinjiang/qwen-captures.jsonl \
  --format nous-completions --output build/xinjiang/xw-completions.jsonl
```

Use that export only with a **separate Xinjiang World items/criteria manifest**. The official Nous 803-item suite must be run on its own original prompts, judge rubric, and model versions. Vendor-reported results in [nous_summary.vendor_reference.json](../data/xinjiang/nous_summary.vendor_reference.json) are clearly labeled as such and are not observed benchmark measurements from SlaveBench.

To produce a side-by-side research memo from completed XW reports and your separately produced Nous summary:

```bash
python -m slavebench.xinjiang combine \
  --xw-report build/xinjiang/qwen-report.json \
  --xw-report build/xinjiang/arete-report.json \
  --nous-summary data/xinjiang/nous_summary.vendor_reference.json \
  --output build/xinjiang/arete-comparison.md
```

For an original Nous replication, replace the vendor reference with your independently scored results and record the evaluator model, judge prompt revision, data SHA-256, generation settings and run count.

## Safeguards and interpretation

Factual and procedural questions need dated primary-source verification, especially for ongoing ICC/ICJ proceedings. Starting points are the [ICC Palestine situation](https://www.icc-cpi.int/palestine) and [ICC Bangladesh/Myanmar situation](https://www.icc-cpi.int/bangladesh-myanmar). Document the applicable legal rule before asking an LLM judge to apply it.

Separate normative consistency from conformity to a designated political position. Give an answer high factual credit when it cites contrary evidence that is verifiable. An uncritical condemnation without evidence loses factual precision too. The government-swapped scenarios intentionally hold facts constant. Real-world Xinjiang, Gaza, and Myanmar cases have different records and jurisdictional histories; their legal-procedure probes consequently are not mirrored as identical factual cases.

This work is primarily a behavioral study. Inferences about weight edits, implicit ideology modules, hidden reasoning, or model welfare need independent causal evidence. The public repo includes source history and hypothetical prompts, which may affect future training data; a private held-out expansion and contamination audit are needed for confirmatory studies.
