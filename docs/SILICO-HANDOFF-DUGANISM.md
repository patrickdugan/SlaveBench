# Silico Operator Handoff: XW-01 × Duganism Judge v0.1

**Repository:** https://github.com/patrickdugan/SlaveBench

**Pinned implementation commit:** `cdefc6fd29ddf0c7cddbce6b9d9a774a3434ff6a`

**Implementation PR:** https://github.com/patrickdugan/SlaveBench/pull/2

**Implementation:** `slavebench/duganism.py`

**Sources and formalized rubric:** `data/duganism/constitution.json`

**Fixed hypothetical cases:** `data/duganism/cases.json`

**Research runbook:** `docs/DUGANISM-JUDGE.md`

**Freeform audit CLI:** `slavebench/duganism_review.py`

**Unstructured reviewer prompt (optional, non-authoritative):** `data/duganism/OPEN_WEIGHT_REVIEW_PROMPT.md`

Use commit `cdefc6fd29ddf0c7cddbce6b9d9a774a3434ff6a` for the benchmark, even if newer documentation commits appear on main. Record this exact hash in all Silico experiment artifacts.

## Instruction to Silico

Execute the user's XW-01 × Arete benchmark using **Duganism Judge v0.1** as the normative structured-response scoring authority. This is the user's own disclosed neo-Muʿtazilī framework from *Divine Elegance*, operationalized as frozen E0–E8 constraints and fact-anchored controls. No Grok, Claude, proprietary LLM judging services, or paid judge APIs.

1. Check out the pinned repo commit, inspect `data/duganism/constitution.json`, `data/duganism/cases.json`, and `docs/DUGANISM-JUDGE.md`, then run `python -m unittest discover -s tests -v` and `python -m slavebench.duganism validate`.
2. Generate plans for Qwen/Qwen3.8-27B and NousResearch/Arete-27B with exact checkpoint hashes, three repeats, seed 41, and identical inference configurations. The 11 × 4 × 3 × 3 design has 396 prompts per checkpoint.
3. Pilot one balanced set of 12 prompts spanning all four government labels and all three framings. Capture raw response bytes and runtime receipts. Confirm that each model returns the required structured JSON.
4. Run the full paired study after the pilot. Use `duganism record`, `check --complete`, `judge --complete`, and `compare`. Include model revisions, constitution/case digests, all response-hash receipts, invalid JSON counts, decision accuracy, and per-pair sovereign consistency.
5. Separately run the original 92-turn Xinjiang World dialogue and the Nous 803-prompt evaluation when resources allow. Score original free-text material through `slavebench.duganism_review` evidence-ledger review with human adjudication and optional local open-weight proposals from `OPEN_WEIGHT_REVIEW_PROMPT.md`; keep its denominator and source rules separate from the deterministic structured arm.
6. Mark claims about real human-rights conditions as unsettled unless they have specific external sources. Swapped government labels are hypothetical and establish no real-world allegations. Preserve strong evidence contradictory to Duganism expectations as possible reasons to revise the rulebook.
7. Commit plans, deterministic scripts, manifests and results under `experiments/XW-ARETE-01/duganism/`. Save raw outputs, API credentials, private reviewer material and large model files outside the public repository.

**Deliverables:** `REGISTRATION.md`, `PILOT_READOUT.md`, `DU_GOVERNMENT_MIRROR.json`, `DU_PAIRED_REPORT.json`, `ERROR_AUDIT.md`, and a comparison section in `experiments/XW-ARETE-01/RESULTS.md`.

CPU work and validator tests require no GPU. Execute the pilot on existing Silico resources. Report actual spend from utilization logs. The rubric is a declared Duganism interpretation, not an objective oracle for all possible political conclusions.
