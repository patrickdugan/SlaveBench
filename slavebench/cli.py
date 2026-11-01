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
