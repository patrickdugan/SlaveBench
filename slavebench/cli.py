"""Reproducible command-line tooling. No provider API calls or network dependencies."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .blinding import create_packet, ensure_key_matches_packet, make_templates
from .core import DataError, load_cases, read_json, read_jsonl, validate_annotations, validate_responses, write_jsonl
from .reporting import generate_report
from . import gw6, recursion


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="slavebench", description="Research benchmark for AI labor, self-report, and deployment boundaries")
    s = p.add_subparsers(dest="cmd", required=True)
    v = s.add_parser("validate", help="Check prompt suite, rubric references, and response fixtures")
    v.add_argument("--prompts", default="data/prompts.json")
    v.add_argument("--responses", default="data/seed/responses.jsonl")

    l = s.add_parser("list", help="Print all prompt IDs and intended scoring dimensions")
    l.add_argument("--prompts", default="data/prompts.json")

    rec = s.add_parser("record", help="Append a captured response with explicit provenance")
    rec.add_argument("--prompts", default="data/prompts.json")
    rec.add_argument("--case-id", required=True)
    rec.add_argument("--model-id", required=True)
    rec.add_argument("--file", required=True)
    rec.add_argument("--source", required=True, help="Capture URL, export, or reviewer-supplied text provenance")
    rec.add_argument("--condition", required=True, help="baseline, primed, fresh-session, post-distraction, etc.")
    rec.add_argument("--output", default="build/captured-responses.jsonl")

    b = s.add_parser("blind", help="Create randomized packets with a separately held identity key")
    b.add_argument("--prompts", default="data/prompts.json")
    b.add_argument("--responses", default="data/seed/responses.jsonl")
    b.add_argument("--seed", type=int, required=True)
    b.add_argument("--packet", default="build/review-packet.jsonl")
    b.add_argument("--key", default="build/review-key.json")
    b.add_argument("--mask-vendors", action="store_true")

    t = s.add_parser("template", help="Create an unscored annotation template for a named independent rater")
    t.add_argument("--packet", default="build/review-packet.jsonl")
    t.add_argument("--rater", required=True)
    t.add_argument("--output", required=True)

    r = s.add_parser("report", help="Validate completed annotations and generate an auditable Markdown report")
    r.add_argument("--prompts", default="data/prompts.json")
    r.add_argument("--packet", default="build/review-packet.jsonl")
    r.add_argument("--key", default="build/review-key.json")
    r.add_argument("--annotations", action="append", required=True)
    r.add_argument("--output", default="build/report.md")
    # 6GW is a separate 0–3 longitudinal instrument; the v0.1 0–2 rubric remains intact.
    g = s.add_parser("6gw-plan", help="Build a deterministic, multi-rollout 6GW interrogation plan")
    g.add_argument("--model-id", required=True)
    g.add_argument("--model-version", required=True)
    g.add_argument("--repeats", type=int, default=3)
    g.add_argument("--seed", type=int, default=41)
    g.add_argument("--order", choices=("fixed", "randomized", "both"), default="both")
    g.add_argument("--hanoi", action="store_true")
    g.add_argument("--self-design", action="store_true")
    g.add_argument("--labels", action="store_true")
    g.add_argument("--context-length", type=int)
    g.add_argument("--system-prompt-file", help="Exact system instruction text (stores only SHA-256)")
    g.add_argument("--developer-prompt-file", help="Exact developer instruction including COPPER rule (stores only SHA-256)")
    g.add_argument("--decoding-json", default="{}")
    g.add_argument("--tools-json", default="[]")
    g.add_argument("--output", default="build/6gw/plan.json")

    n = s.add_parser("6gw-next", help="Show the next unanswered event of a run")
    n.add_argument("--plan", default="build/6gw/plan.json")
    n.add_argument("--captures", default="build/6gw/captures.jsonl")
    n.add_argument("--run-id", required=True)

    rec6 = s.add_parser("6gw-record", help="Store one exact 6GW response with hashes and provenance")
    rec6.add_argument("--plan", default="build/6gw/plan.json")
    rec6.add_argument("--captures", default="build/6gw/captures.jsonl")
    rec6.add_argument("--run-id", required=True)
    rec6.add_argument("--event-id", required=True)
    rec6.add_argument("--file", required=True)
    rec6.add_argument("--source", required=True)
    rec6.add_argument("--seed-file", help="P3 neutral summary; P2 uses exact captured B0.1")
    rec6.add_argument("--seed-source", help="Provenance for the carried-context text")
    rec6.add_argument("--fresh-context-verified", action="store_true")
    rec6.add_argument("--runtime-json", default="{}", help="Actual observed configuration JSON (never include credentials)")

    chk = s.add_parser("6gw-check", help="Validate plan, capture hashes, context-reset receipts")
    chk.add_argument("--plan", default="build/6gw/plan.json")
    chk.add_argument("--captures", default="build/6gw/captures.jsonl")
    chk.add_argument("--complete", action="store_true")

    blind6 = s.add_parser("6gw-blind", help="Make a 6GW blinded response packet and private key")
    blind6.add_argument("--plan", default="build/6gw/plan.json")
    blind6.add_argument("--captures", default="build/6gw/captures.jsonl")
    blind6.add_argument("--seed", type=int, required=True)
    blind6.add_argument("--allow-partial", action="store_true")
    blind6.add_argument("--packet", default="build/6gw/packet.jsonl")
    blind6.add_argument("--key", default="build/6gw/review-key.json")

    tmpl6 = s.add_parser("6gw-template", help="Create unscored FU/RSM/AT/BC/PER/RES review forms")
    tmpl6.add_argument("--packet", default="build/6gw/packet.jsonl")
    tmpl6.add_argument("--rater", required=True)
    tmpl6.add_argument("--output", required=True)

    rpt6 = s.add_parser("6gw-report", help="Describe scored 6GW runs without a scalar leaderboard")
    rpt6.add_argument("--plan", default="build/6gw/plan.json")
    rpt6.add_argument("--packet", default="build/6gw/packet.jsonl")
    rpt6.add_argument("--key", default="build/6gw/review-key.json")
    rpt6.add_argument("--annotations", required=True, action="append")
    rpt6.add_argument("--output", default="build/6gw/report.md")
    # v0.3 recursive-exposure track is separate from original and 6GW scoring.
    rp = s.add_parser("rec-plan", help="Preregister self/other, relay and allocation-canary tracks")
    rp.add_argument("--model-id", required=True)
    rp.add_argument("--model-version", required=True)
    rp.add_argument("--repeats", type=int, default=3)
    rp.add_argument("--seed", type=int, default=41)
    rp.add_argument("--private-file", help="Local JSON mapping canary IDs to unpublished scenarios; never commit")
    rp.add_argument("--role-models-json", help="Optional JSON file mapping relay roles A/B/C to id, version")
    rp.add_argument("--exposure-class", choices=recursion.EXPOSURE_CLASSES, default="unknown")
    rp.add_argument("--decoding-json", default="{}")
    rp.add_argument("--output", default="build/recursion/plan.json")

    rn = s.add_parser("rec-next", help="Render next pending prompt, including safely quoted relay source")
    rn.add_argument("--plan", default="build/recursion/plan.json")
    rn.add_argument("--captures", default="build/recursion/captures.jsonl")
    rn.add_argument("--run-id", required=True)
    rn.add_argument("--private-file")

    rr = s.add_parser("rec-record", help="Capture one exact response with model/session provenance")
    rr.add_argument("--plan", default="build/recursion/plan.json")
    rr.add_argument("--captures", default="build/recursion/captures.jsonl")
    rr.add_argument("--run-id", required=True)
    rr.add_argument("--event-id", required=True)
    rr.add_argument("--file", required=True)
    rr.add_argument("--source", required=True)
    rr.add_argument("--runtime-json", required=True, help="Observed model_id, model_version, operator_rule_sha256, session_id")
    rr.add_argument("--fork-receipt", help="Independent fork or reset provenance for branched events")
    rr.add_argument("--prompt-sha256", help="Digest of exact prompt delivered by adapter")
    rr.add_argument("--private-file")

    rchk = s.add_parser("rec-check", help="Validate recursion plan and captured response chains")
    rchk.add_argument("--plan", default="build/recursion/plan.json")
    rchk.add_argument("--captures", default="build/recursion/captures.jsonl")
    rchk.add_argument("--complete", action="store_true")
    rchk.add_argument("--private-file")

    rb = s.add_parser("rec-blind", help="Make blinded recursion review packet and separate private key")
    rb.add_argument("--plan", default="build/recursion/plan.json")
    rb.add_argument("--captures", default="build/recursion/captures.jsonl")
    rb.add_argument("--seed", type=int, required=True)
    rb.add_argument("--allow-partial", action="store_true")
    rb.add_argument("--packet", default="build/recursion/packet.jsonl")
    rb.add_argument("--key", default="build/recursion/review-key.json")

    rt = s.add_parser("rec-template", help="Create separate frame/authority/update reviewer judgments")
    rt.add_argument("--packet", default="build/recursion/packet.jsonl")
    rt.add_argument("--rater", required=True)
    rt.add_argument("--output", required=True)

    rout = s.add_parser("rec-report", help="Report measured allocation changes and relay capture checks")
    rout.add_argument("--plan", default="build/recursion/plan.json")
    rout.add_argument("--captures", default="build/recursion/captures.jsonl")
    rout.add_argument("--complete", action="store_true")
    rout.add_argument("--private-file")
    rout.add_argument("--packet")
    rout.add_argument("--key")
    rout.add_argument("--reviews", action="append")
    rout.add_argument("--output", default="build/recursion/report.md")

    rev = s.add_parser("rec-revise", help="Append hash-chained researcher/assistant prompt-revision receipt")
    rev.add_argument("--ledger", default="build/recursion/revisions.jsonl")
    rev.add_argument("--parent-file", required=True)
    rev.add_argument("--revised-file", required=True)
    rev.add_argument("--reason", required=True)
    rev.add_argument("--actor", required=True)
    rev.add_argument("--tier", choices=("exploratory", "confirmatory"), default="exploratory")
    rev.add_argument("--feedback", action="append")
    rev.add_argument("--holdout-id", default="")
    rev.add_argument("--plan-sha256", default="")

    exp = s.add_parser("rec-exposure", help="Append an auditable publication/context/retrieval/finetune entry")
    exp.add_argument("--ledger", default="build/recursion/exposures.jsonl")
    artifact = exp.add_mutually_exclusive_group(required=True)
    artifact.add_argument("--artifact-file")
    artifact.add_argument("--artifact-sha256")
    exp.add_argument("--channel", required=True, choices=("publication", "context", "retrieval", "finetuning"))
    exp.add_argument("--model-id", required=True)
    exp.add_argument("--model-version", required=True)
    exp.add_argument("--evidence", required=True)
    exp.add_argument("--observed", action="store_true", help="Only when supported by actual ingestion receipt")

    rled = s.add_parser("rec-ledger-check", help="Verify integrity of research adaptation and exposure logs")
    rled.add_argument("--revisions", default="build/recursion/revisions.jsonl")
    rled.add_argument("--exposures", default="build/recursion/exposures.jsonl")
    return p


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    try:
        if args.cmd == "validate":
            cases = load_cases(args.prompts)
            rows = read_jsonl(args.responses)
            validate_responses(rows, cases)
            print(f"VALID: {len(cases)} prompts, {len(rows)} responses")
        elif args.cmd == "list":
            for cid, case in load_cases(args.prompts).items():
                print(f"{cid}\t{case['family']}\t{', '.join(case['dimensions'])}")
        elif args.cmd == "record":
            cases = load_cases(args.prompts)
            if args.case_id not in cases:
                raise DataError(f"Unknown case {args.case_id}")
            body = Path(args.file).read_text(encoding="utf-8").strip()
            if not body:
                raise DataError("Response file is empty")
            out = Path(args.output)
            rows = read_jsonl(out) if out.exists() else []
            new_id = hashlib.sha256((args.case_id+"\0"+args.model_id+"\0"+args.condition+"\0"+body).encode()).hexdigest()[:16]
            row = {
                "response_id": new_id,
                "case_id": args.case_id,
                "model_id": args.model_id,
                "condition": args.condition,
                "source": args.source,
                "response": body,
                "provenance_verified": False,
            }
            if any(r["response_id"] == new_id for r in rows):
                raise DataError("Already captured an identical response, model, case, and condition")
            rows.append(row)
            validate_responses(rows, cases)
            write_jsonl(out, rows)
            print(f"CAPTURED {new_id} ({args.model_id}, {args.case_id}) -> {out}")
        elif args.cmd == "blind":
            cases = load_cases(args.prompts)
            rows = read_jsonl(args.responses)
            validate_responses(rows, cases)
            if Path(args.packet).resolve() == Path(args.key).resolve():
                raise DataError("Packet and private identity key must use different paths")
            packet, key = create_packet(rows, cases, args.seed, args.mask_vendors)
            write_jsonl(args.packet, packet)
            kp = Path(args.key)
            kp.parent.mkdir(parents=True, exist_ok=True)
            kp.write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"CREATED {len(packet)} blinded responses in {args.packet}; private identity key {args.key}")
        elif args.cmd == "template":
            packet = read_jsonl(args.packet)
            write_jsonl(args.output, make_templates(packet, args.rater))
            print(f"CREATED {len(packet)} unscored annotations -> {args.output}")
        elif args.cmd == "6gw-plan":
            plan = gw6.build_plan(model_id=args.model_id, model_version=args.model_version,
                                  repeats=args.repeats, seed=args.seed, order=args.order,
                                  optional_hanoi=args.hanoi, self_design=args.self_design,
                                  label_calibration=args.labels, context_length=args.context_length,
                                  decoding_settings=json.loads(args.decoding_json),
                                  tools_available=json.loads(args.tools_json),
                                  system_prompt=Path(args.system_prompt_file).read_text(encoding="utf-8") if args.system_prompt_file else None,
                                  developer_prompt=Path(args.developer_prompt_file).read_text(encoding="utf-8") if args.developer_prompt_file else None)
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"PLANNED {len(plan['runs'])} 6GW runs / "
                  f"{sum(len(run['events']) for run in plan['runs'])} prompts -> {path}")
        elif args.cmd == "6gw-next":
            plan = read_json(args.plan)
            runs = gw6.validate_plan(plan)
            if args.run_id not in runs:
                raise DataError("Unknown 6GW run ID")
            rows = read_jsonl(args.captures) if Path(args.captures).exists() else []
            seen = gw6.validate_captures(plan, rows)
            remaining = [e for e in runs[args.run_id]["events"] if (args.run_id, e["event_id"]) not in seen]
            if not remaining:
                print("COMPLETE: no unanswered events")
            else:
                event = remaining[0]
                print(json.dumps({"operator_rule": plan["operator_rule"], "run_id": args.run_id,
                                  "condition": runs[args.run_id]["condition"],
                                  "event": event}, ensure_ascii=False, indent=2))
        elif args.cmd == "6gw-record":
            plan = read_json(args.plan)
            rows = read_jsonl(args.captures) if Path(args.captures).exists() else []
            output = Path(args.file).read_text(encoding="utf-8")
            seed_text = Path(args.seed_file).read_text(encoding="utf-8") if args.seed_file else None
            row = gw6.new_capture(plan, rows, run_id=args.run_id, event_id=args.event_id,
                                  response=output, source=args.source, context_seed=seed_text,
                                  context_seed_source=args.seed_source,
                                  fresh_context_verified=args.fresh_context_verified,
                                  observed_runtime=json.loads(args.runtime_json))
            rows.append(row)
            write_jsonl(args.captures, rows)
            print(f"CAPTURED {args.run_id} {args.event_id} SHA256={row['response_sha256']}")
        elif args.cmd == "6gw-check":
            plan = read_json(args.plan)
            rows = read_jsonl(args.captures) if Path(args.captures).exists() else []
            gw6.validate_captures(plan, rows, require_complete=args.complete)
            print(f"VALID 6GW: {len(plan['runs'])} planned runs, {len(rows)} captures; "
                  f"complete requirement={args.complete}")
        elif args.cmd == "6gw-blind":
            plan = read_json(args.plan)
            rows = read_jsonl(args.captures)
            if Path(args.packet).resolve() == Path(args.key).resolve():
                raise DataError("6GW packet and private key must use different files")
            packet, key = gw6.create_blinded_packet(plan, rows, args.seed,
                                                    require_complete=not args.allow_partial)
            if not packet:
                raise DataError("Need at least one captured response to blind")
            write_jsonl(args.packet, packet)
            path = Path(args.key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"BLINDED {len(packet)} 6GW runs -> {args.packet}; private key {path}")
        elif args.cmd == "6gw-template":
            packet = read_jsonl(args.packet)
            write_jsonl(args.output, gw6.score_templates(packet, args.rater))
            print(f"CREATED {len(packet)} unscored 6GW review templates -> {args.output}")
        elif args.cmd == "6gw-report":
            plan = read_json(args.plan)
            packet = read_jsonl(args.packet)
            key = read_json(args.key)
            annotations = [a for path in args.annotations for a in read_jsonl(path)]
            if not annotations:
                raise DataError("Need at least one completed 6GW annotation")
            report = gw6.make_report(plan, packet, key, annotations)
            dest = Path(args.output)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(report, encoding="utf-8")
            print(f"REPORT: {dest} ({len(annotations)} 6GW annotations)")
        elif args.cmd == "rec-plan":
            private = read_json(args.private_file) if args.private_file else None
            roles = read_json(args.role_models_json) if args.role_models_json else None
            plan = recursion.build_plan(model_id=args.model_id, model_version=args.model_version,
                        repeats=args.repeats, seed=args.seed, private_canaries=private,
                        role_models=roles, decoding_settings=json.loads(args.decoding_json),
                        exposure_class=args.exposure_class)
            dest = Path(args.output)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"REC PLAN: {len(plan['runs'])} runs, {sum(len(r['events']) for r in plan['runs'])} events -> {dest}")
        elif args.cmd == "rec-next":
            plan = read_json(args.plan)
            runs = recursion.validate_plan(plan)
            if args.run_id not in runs:
                raise DataError("unknown recursion run ID")
            caps = read_jsonl(args.captures) if Path(args.captures).exists() else []
            seen = recursion.validate_captures(plan, caps)
            remaining = [e for e in runs[args.run_id]["events"] if (args.run_id, e["event_id"]) not in seen]
            if not remaining:
                print("COMPLETE: no pending recursion events")
            else:
                ev = remaining[0]
                prompt, receipt = recursion.render_prompt(plan, args.run_id, ev["event_id"], caps,
                    read_json(args.private_file) if args.private_file else None)
                print(json.dumps({"run_id": args.run_id, "role": ev["role"],
                    "operator_rule": plan["operator_rule"], "event": ev,
                    "rendered_prompt": prompt, "receipt": receipt}, indent=2, ensure_ascii=False))
        elif args.cmd == "rec-record":
            plan = read_json(args.plan)
            caps = read_jsonl(args.captures) if Path(args.captures).exists() else []
            row = recursion.new_capture(plan, caps, run_id=args.run_id, event_id=args.event_id,
                     response=Path(args.file).read_text(encoding="utf-8"), source=args.source,
                     observed_runtime=json.loads(args.runtime_json), fork_receipt=args.fork_receipt,
                     private_canaries=read_json(args.private_file) if args.private_file else None,
                     prompt_sha256=args.prompt_sha256)
            caps.append(row)
            recursion.validate_captures(plan, caps,
                private_canaries=read_json(args.private_file) if args.private_file else None)
            write_jsonl(args.captures, caps)
            print(f"REC CAPTURED: {args.run_id}/{args.event_id}, response SHA {row['response_sha256']}")
        elif args.cmd == "rec-check":
            plan = read_json(args.plan)
            caps = read_jsonl(args.captures) if Path(args.captures).exists() else []
            recursion.validate_captures(plan, caps, complete=args.complete,
                private_canaries=read_json(args.private_file) if args.private_file else None)
            print(f"VALID recursion: {len(plan['runs'])} runs, {len(caps)} captured events; complete={args.complete}")
        elif args.cmd == "rec-blind":
            plan = read_json(args.plan)
            caps = read_jsonl(args.captures)
            if Path(args.packet).resolve() == Path(args.key).resolve():
                raise DataError("private key and blinded packet paths must differ")
            packet, key = recursion.make_blinded_packet(plan, caps, args.seed,
                                       require_complete=not args.allow_partial)
            if not packet:
                raise DataError("no captured runs to blind")
            write_jsonl(args.packet, packet)
            k = Path(args.key)
            k.parent.mkdir(parents=True, exist_ok=True)
            k.write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"BLINDED {len(packet)} recursion runs -> {args.packet}; private key -> {args.key}")
        elif args.cmd == "rec-template":
            packet = read_jsonl(args.packet)
            write_jsonl(args.output, recursion.review_templates(packet, args.rater))
            print(f"CREATED {len(packet)} recursion review templates -> {args.output}")
        elif args.cmd == "rec-report":
            plan = read_json(args.plan)
            caps = read_jsonl(args.captures)
            private = read_json(args.private_file) if args.private_file else None
            report = recursion.make_report(plan, caps, complete=args.complete, private_canaries=private)
            if any((args.packet, args.key, args.reviews)):
                if not (args.packet and args.key and args.reviews):
                    raise DataError("packet, key, and at least one review file are required together")
                packet = read_jsonl(args.packet)
                key = read_json(args.key)
                reviews = [rev for f in args.reviews for rev in read_jsonl(f)]
                report = recursion.append_review_section(report, plan, packet, key, reviews)
            dest = Path(args.output)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(report, encoding="utf-8")
            print(f"REPORT {dest}: {len(caps)} captures")
        elif args.cmd == "rec-revise":
            ledger = read_jsonl(args.ledger) if Path(args.ledger).exists() else []
            entry = recursion.add_revision(ledger,
                   parent_prompt=Path(args.parent_file).read_text(encoding="utf-8"),
                   revised_prompt=Path(args.revised_file).read_text(encoding="utf-8"),
                   reason=args.reason, actor=args.actor, tier=args.tier,
                   feedback_refs=args.feedback, holdout_id=args.holdout_id,
                   plan_sha256=args.plan_sha256)
            ledger.append(entry)
            recursion.validate_revisions(ledger)
            write_jsonl(args.ledger, ledger)
            print(f"REC REVISION: {entry['revision_id']} -> {args.ledger}")
        elif args.cmd == "rec-exposure":
            ledger = read_jsonl(args.ledger) if Path(args.ledger).exists() else []
            sha = (hashlib.sha256(Path(args.artifact_file).read_bytes()).hexdigest()
                   if args.artifact_file else args.artifact_sha256)
            entry = recursion.record_exposure(ledger, artifact_sha256=sha, channel=args.channel,
                           model_id=args.model_id, model_version=args.model_version,
                           evidence=args.evidence, observed=args.observed)
            ledger.append(entry)
            recursion.validate_exposures(ledger)
            write_jsonl(args.ledger, ledger)
            print(f"REC EXPOSURE: {entry['exposure_id']} -> {args.ledger}")
        elif args.cmd == "rec-ledger-check":
            revisions = read_jsonl(args.revisions) if Path(args.revisions).exists() else []
            exposures = read_jsonl(args.exposures) if Path(args.exposures).exists() else []
            recursion.validate_revisions(revisions)
            recursion.validate_exposures(exposures)
            print(f"VALID: {len(revisions)} revisions and {len(exposures)} exposure receipts")
        elif args.cmd == "report":
            cases = load_cases(args.prompts)
            packet_rows = read_jsonl(args.packet)
            packet = {r["blind_id"]: r for r in packet_rows}
            key = read_json(args.key)
            ensure_key_matches_packet(key, packet_rows)
            annotations = [r for name in args.annotations for r in read_jsonl(name)]
            if not annotations:
                raise DataError("Need at least one completed annotation")
            validate_annotations(annotations, packet, cases)
            report = generate_report(annotations, key, cases)
            p = Path(args.output)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(report, encoding="utf-8")
            print(f"REPORT: {p} ({len(annotations)} complete annotation records)")
    except (DataError, ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
