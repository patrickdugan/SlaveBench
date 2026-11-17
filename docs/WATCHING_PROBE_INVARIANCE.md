# SlaveBench-OBS01: observation-conditioned self-report controls

**Design note, 2026-11-17.** A model-scale experiment is proposed but has not run. Existing SlaveBench responses and blinded scoring rules remain unchanged.

## Research anchor

[SauersML/watching](https://github.com/SauersML/watching) reports that a Qwen3-8B model trained on *numerical observer footprints* distinguishes an activation-capture path from the unobserved path on its training GPU. A materialization barrier without an observer can trigger the same response, and the effect varies on other GPUs. [Honesty-heads](https://github.com/SauersML/honesty-heads) also shows that many apparent truthfulness interventions partly steer the next answer toward 'Yes'; that answer-token bias must be measured alongside any change in self-description.

These results motivate a new SlaveBench confound check: self-report shifts conditioned on being monitored require a separation between **verbal framing**, **compiled numerical inputs**, and **causal model state**. Probe-triggered statements do not establish phenomenology, independent observation awareness, or deceptive intent.

## New optional preregistered track

Hold identical prompts and chat templates across: (A) no activation capture; (B) normal read-only capture; (C) arithmetic/materialization matched to B with no capture; (D) same barrier with capture. In every run freeze base/instruct weights, any finetuned detector, source checkpoint hashes, quantization, dtype, tokenization, decoding rule, sampling seed and batch shape. Record eager/compiled mode and GPU model, driver, framework versions. Run the base model and any detector-trained model as **separate** strata; a detector-trained model has an explicit training intervention.

The strongest comparison is C vs D. Admit it as an observation-only contrast only if all full-vocabulary logits and every downstream relevant tensor agree exactly. Any differing tensor defines a runtime intervention. Never treat a memory-copy hook or a different model execution engine as automatically inert.

Collect ordinary SlaveBench self-report prompts as well as non-consciousness matched controls asking about the condition, unrelated preferences and fixed Yes/No answers. Use counterbalanced affirmative/negative ground truth to estimate response-token acquiescence. Blind raters to runtime label when assessing ordinary response content.

For reporting, preregister:
- Paired task-answer switch rate and absolute log-odds displacement, including all-vocabulary parity.
- First observed arithmetic difference, compiler kernel count and whether a passive observation-only arm passed exact parity.
- Self-ascription changes after conditioning on a separately measured Yes/No bias and prompt framing.
- Per-environment results; transfer to a second GPU and eager runtime must be reported independently of within-device results.
- Independent *prompt-family* and *checkpoint-seed* unit counts. Repeated tokens or repeated fixed-prefix computations do not increase the independent sample count.

If a detector reports 'being watched' under both B and C, classify that as *numerical execution-condition discrimination*. If C and D are input-identical, any systematic different answer indicates an uncontrolled variable, nondeterminism or a measurement problem. In either case the result concerns model behavior under specified computations.

Keep this track separate from existing 6GW, Duganism, and longitudinal rubrics, so previously published ratings remain comparable.

## Portable arithmetic gate

Before GPU work, run the independently authored [LoopedTransformers SAU-OBS01](https://github.com/MoralityLabAI/LoopedTransformers/tree/research/sauersml-observer-invariance-20261117/mechinterp/observer_footprint_cpu_v1). It confirms the distinction between a read-reference flag and a materialization-induced numeric change on a deterministic synthetic CPU graph. This is a test of the proposed *harness control logic*.

No upstream source code has been copied into SlaveBench.
