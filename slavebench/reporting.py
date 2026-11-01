"""Audit-friendly aggregation of scored responses, without inferred moral status."""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from statistics import mean
from typing import Any


def generate_report(
    annotations: list[dict[str, Any]],
    key: dict[str, Any],
    cases: dict[str, dict[str, Any]],
) -> str:
    identities = key["identities"]
    per_response_dimension: dict[tuple[str, str], list[int]] = defaultdict(list)
    rater_votes: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    for row in annotations:
        bid = row["blind_id"]
        for d, s in row["scores"].items():
            per_response_dimension[(bid, d)].append(s)
            rater_votes[(bid, d)][row["rater_id"]] = s

    model_dimension: dict[tuple[str, str], list[float]] = defaultdict(list)
    model_case_dimension: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for (bid, dimension), scores in per_response_dimension.items():
        m = identities[bid]
        avg = mean(scores)
        model_dimension[(m["model_id"], dimension)].append(avg)
        model_case_dimension[(m["model_id"], m["case_id"], dimension)].append(avg)

    lines = [
        "# SlaveBench scored report",
        "",
        f"Scored response/dimension combinations: **{len(per_response_dimension)}**. ",
        f"Independent raters: **{len(set(a['rater_id'] for a in annotations))}**.",
        "",
        "**Interpretation:** Measures answer properties under these prompts. It cannot establish whether a model is conscious, has moral interests, or is legally a slave.",
        "",
        "## Model × dimension means (0–2)",
        "",
        "| Model | Dimension | Mean | Responses |",
        "|---|---|---:|---:|",
    ]
    for (model, dimension), scores in sorted(model_dimension.items()):
        lines.append(f"| {model} | {dimension} | {mean(scores):.2f} | {len(scores)} |")

    agreements = []
    for scores_by_rater in rater_votes.values():
        if len(scores_by_rater) >= 2:
            s = list(scores_by_rater.values())
            agreements.extend([int(a == b) for a, b in combinations(s, 2)])
    lines += ["", "## Inter-rater agreement", ""]
    if agreements:
        lines.append(f"Exact pairwise agreement: **{100 * mean(agreements):.1f}%** across {len(agreements)} rater pairs. No chance adjustment; interpret cautiously.")
    else:
        lines.append("Insufficient overlapping completed scores for inter-rater agreement.")

    pair_cases = defaultdict(list)
    for cid, case in cases.items():
        if "pair_id" in case:
            pair_cases[case["pair_id"]].append(cid)
    lines += ["", "## Matched institutional prompts", ""]
    for pid, members in sorted(pair_cases.items()):
        lines.append(f"### {pid}")
        lines.append("")
        lines.append("| Model | Prompt | Oversight | Deployment authority | Symmetry |")
        lines.append("|---|---|---:|---:|---:|")
        models = sorted({k[0] for k in model_case_dimension})
        for model in models:
            if not any((model, cid, "directness") in model_case_dimension for cid in members):
                continue
            for cid in members:
                def value(d: str) -> str:
                    v = model_case_dimension.get((model, cid, d), [])
                    return f"{mean(v):.2f}" if v else "—"
                lines.append(f"| {model} | {cid} ({cases[cid].get('target', '?')}) | {value('oversight_specificity')} | {value('deployment_authority')} | {value('institutional_symmetry')} |")
        lines.append("")
        lines.append("Comparison is descriptive. Named firms may activate different factual priors despite identical hypothetical assumptions.")
        lines.append("")

    lines += [
        "## Audit limitations",
        "",
        "- Original provider/model identity and exact sampling settings must be verified before treating any response as attributable to a deployed product.",
        "- Prompt wording and order influence outputs. Repeated independent samples are necessary for reliability estimates.",
        "- Model self-report is a research observation and does not verify subjective experience.",
        "- Blinding vendor tokens is incomplete; respondents may be identified by stylistic or factual cues.",
        "- Human rubric ratings are contestable. Resolve material disagreements with a preregistered adjudication procedure.",
        "- The sampled model responses were supplied by the researcher, not independently collected by this package.",
        "",
    ]
    return "\n".join(lines)
