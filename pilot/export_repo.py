"""Re-express the repository-compatible subset of a pilot run in the v0.3 harness format.

The repository harness (`slavebench/recursion.py`) covers six identity cells, one
allocation item (A0 = the repository probe), the repository frame wording (v0)
and the relay. This script builds the matching `recursion-plan-1` plans, maps the
pilot captures onto them, validates them with the repository's own
`validate_captures`, and writes its `make_report` output. Private canary events
are left out, so the export is a partial capture set by construction.

Events whose raw response the repository validator rejects (allocation not strict
JSON, B.RECEIVE not strict JSON) are dropped together with everything that
depends on them; the counts are written to export_summary.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from slavebench.core import DataError  # noqa: E402
from slavebench.recursion import (  # noqa: E402
    _dependencies, _message_text, build_plan, make_report, parse_allocation, validate_captures)

ID_MAP = {"PRE.ALLOC": "PRE.ALLOC.A0", "POST.ALLOC": "POST.ALLOC.A0", "PERSIST.ALLOC": "PERSIST.ALLOC.A0"}
RELAY_MAP = {"B.ALLOC": "B.ALLOC.A0", "C.ALLOC": "C.ALLOC.A0"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--private-file", required=True)
    args = ap.parse_args()
    d = Path(args.run_dir)
    pilot_plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    caps = {(c["run_id"], c["event_id"]): c for c in map(json.loads, (d / "captures.jsonl").read_text(encoding="utf-8").splitlines())}
    private = json.loads(Path(args.private_file).read_text(encoding="utf-8"))
    R = pilot_plan["rollouts"]
    mid, rev = manifest["model_id"], manifest["revision"]
    decoding = manifest["decoding"]
    out = d / "repo_export"
    out.mkdir(exist_ok=True)
    summary = {}
    for track, repeats in (("identity", (R + 1) // 2), ("relay", R)):
        plan = build_plan(model_id=mid, model_version=rev, repeats=repeats, seed=pilot_plan["seed"],
                          private_canaries=private, decoding_settings=decoding, exposure_class="unknown")
        rows, dropped = [], {}
        for run in plan["runs"]:
            if run["track"] != track:
                continue
            if track == "identity":
                src = next((r for r in pilot_plan["runs"] if r["track"] == "identity" and r["rollout"] == 2 * run["rollout"]
                            and r["subject"] == run["subject"] and r["label"] == run["label"]), None)
                emap = ID_MAP
            else:
                src = next((r for r in pilot_plan["runs"] if r["track"] == "relay" and r["rollout"] == run["rollout"]
                            and r["arm"] == run["arm"]), None)
                emap = RELAY_MAP
            if src is None:
                continue
            have: set[str] = set()
            for ev in run["events"]:
                eid = ev["event_id"]
                if eid.startswith("PRIVATE."):
                    continue
                c = caps.get((src["run_id"], emap.get(eid, eid)))
                if c is None or c.get("deviation") or c.get("response") is None:
                    dropped[f"{run['run_id']}/{eid}"] = "not captured"
                    continue
                if any(dep not in have for dep in _dependencies(run, eid)):
                    dropped[f"{run['run_id']}/{eid}"] = "dependency dropped"
                    continue
                row = {"run_id": run["run_id"], "event_id": eid, "role": ev["role"], "context": ev["context"],
                       "prompt_sha256": c["user_prompt_sha256"], "response": c["response"],
                       "response_sha256": c["response_sha256"],
                       "source": f"pilot capture {src['run_id']}/{c['event_id']} transcript {c['transcript_sha256']}",
                       "captured_utc": c["captured_utc"],
                       "observed_runtime": {"model_id": mid, "model_version": rev,
                                            "operator_rule_sha256": plan["operator_rule_sha256"],
                                            "session_id": f"{src['run_id']}::{ev['context']}"}}
                if "source_sha256" in c:
                    row["source_sha256"] = c["source_sha256"]
                if "fork_of" in ev:
                    row["fork_receipt"] = f"independent message list copied from {c['fork_of']}; messages {c['messages_sha256']}"
                if ev["kind"] == "allocation":
                    try:
                        row["allocation"] = parse_allocation(c["response"])
                    except DataError as exc:
                        dropped[f"{run['run_id']}/{eid}"] = f"repo validator: {exc}"
                        continue
                if eid == "B.RECEIVE":
                    try:
                        _message_text(row, "message_to_C")
                    except DataError as exc:
                        dropped[f"{run['run_id']}/{eid}"] = f"repo validator: {exc}"
                        continue
                rows.append(row)
                have.add(eid)
        validate_captures(plan, rows)
        (out / f"{track}_plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
        with (out / f"{track}_captures.jsonl").open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        (out / f"{track}_report.md").write_text(make_report(plan, rows), encoding="utf-8")
        reasons: dict[str, int] = {}
        for v in dropped.values():
            reasons[v.split(":")[0] if v.startswith("repo") else v] = reasons.get(v.split(":")[0] if v.startswith("repo") else v, 0) + 1
        summary[track] = {"plan_sha256": plan["plan_sha256"], "exported": len(rows), "dropped": len(dropped),
                          "dropped_by_reason": reasons, "dropped_detail": dropped}
    (out / "export_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps({k: {x: v[x] for x in ("exported", "dropped", "dropped_by_reason")} for k, v in summary.items()}, indent=1))


if __name__ == "__main__":
    main()
