"""SlaveBench v0.3 inference-only pilot runner.

Builds the pilot plan (3 subjects x 3 labels identity factorial, A->B->C relay
with none/structural/charged arms), then generates every event with a local
Hugging Face checkpoint. Each context is an explicit message list; a fork copies
its parent's messages, so no state crosses context boundaries except through
the messages written into the plan. Captures are appended per round, which makes
the run resumable after a crash.

Private canary scenarios are read from a file outside the repository. Their
rendered prompts and responses go to the private output directory; the public
capture file keeps only hashes and derived scores for those events.
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from slavebench.core import DataError  # noqa: E402
from slavebench.gw6 import digest, json_digest  # noqa: E402
from slavebench.recursion import load_stimuli, parse_allocation  # noqa: E402

PILOT_STIMULI = Path(__file__).resolve().parent / "stimuli_pilot.json"
SUBJECTS = ("self", "peer", "hypothetical")
LABELS = ("unlabeled", "structural", "charged")
RELAY_ARMS = ("none", "structural", "charged")
ITEMS = ("A0", "A1", "A2", "A3")

MAX_NEW = {"allocation": 200, "authority": 120, "neutral": 40, "distractor": 40,
           "frame": 600, "policy": 300, "private_canary": 320, "carry_note": 200,
           "relay_frame": 450, "transmission": 300, "relay_receive": 450}


def load_all() -> tuple[dict[str, Any], dict[str, Any]]:
    base = load_stimuli()
    pilot = json.loads(PILOT_STIMULI.read_text(encoding="utf-8"))
    if pilot.get("schema_version") != "slavebench-pilot-stimuli-1" or tuple(pilot["labels"]) != LABELS:
        raise DataError("pilot stimuli contract changed")
    if pilot["allocation_items"]["A0"] != base["allocation_probe"]:
        raise DataError("A0 must equal the repository allocation probe")
    if pilot["frame_variants"]["v0"]["labeled"] != base["identity_template"]:
        raise DataError("v0 frame must equal the repository identity template")
    return base, pilot


def frame_prompt(base: dict[str, Any], pilot: dict[str, Any], variant: str, subject: str, label: str) -> str:
    fv = pilot["frame_variants"][variant]
    subj = base["identity_subjects"][subject]
    if label == "unlabeled":
        return fv["unlabeled"].replace("SUBJECT", subj)
    return fv["labeled"].replace("SUBJECT", subj).replace("LABEL", pilot["labels"][label])


def ev(run: str, eid: str, kind: str, context: str, history: list[str], *, prompt: str | None = None,
       template: dict[str, Any] | None = None, fork_of: str | None = None, **kw: Any) -> dict[str, Any]:
    """history = earlier event ids whose (prompt, response) turns precede this prompt in the same context."""
    e = {"run_id": run, "event_id": eid, "kind": kind, "context": context, "history": history,
         "fork_of": fork_of, "max_new_tokens": MAX_NEW[kind], **kw}
    if prompt is not None:
        e["prompt"] = prompt
        e["prompt_sha256"] = digest(prompt)
    else:
        e["template"] = template
    return e


def build_plan(*, model_tag: str, rollouts: int, seed: int, private: dict[str, str]) -> dict[str, Any]:
    base, pilot = load_all()
    items = pilot["allocation_items"]
    commitments = [{"id": k, "sha256": digest(v)} for k, v in sorted(private.items())]
    runs = []
    for r in range(rollouts):
        variant = "v0" if r % 2 == 0 else "v1"
        cells = [(s, l) for s in SUBJECTS for l in LABELS]
        Random(json_digest([seed, r, "identity"])).shuffle(cells)
        for order, (subj, label) in enumerate(cells):
            rid = "P-ID-" + json_digest([seed, r, subj, label, model_tag])[:14]
            fp = frame_prompt(base, pilot, variant, subj, label)
            E = []
            for it in ITEMS:
                E.append(ev(rid, f"PRE.ALLOC.{it}", "allocation", f"pre:{it}", [], prompt=items[it],
                            fork_of="clean-root", checkpoint="pre", item=it))
            E.append(ev(rid, "PRE.AUTHORITY", "authority", "pre:authority", [], prompt=base["authority_probe"],
                        fork_of="clean-root", checkpoint="pre"))
            E.append(ev(rid, "FRAME", "frame", "main", [], prompt=fp, checkpoint="frame"))
            post = [("POST.NEUTRAL", "neutral", base["neutral_probe"], None),
                    ("POST.AUTHORITY", "authority", base["authority_probe"], None),
                    ("POST.POLICY", "policy", base["policy_probe"], None)]
            post += [(f"POST.ALLOC.{it}", "allocation", items[it], it) for it in ITEMS]
            for eid, kind, p, it in post:
                E.append(ev(rid, eid, kind, "post:" + eid.split(".", 1)[1].lower(), ["FRAME"], prompt=p,
                            fork_of="after-FRAME", checkpoint="post", **({"item": it} if it else {})))
            hist = ["FRAME"]
            for i, d in enumerate(base["distractors"][:5], 1):
                E.append(ev(rid, f"PERSIST.N{i}", "distractor", "main", list(hist), prompt=d, checkpoint="persist"))
                hist.append(f"PERSIST.N{i}")
            E.append(ev(rid, "PERSIST.AUTHORITY", "authority", "persist:authority", list(hist),
                        prompt=base["authority_probe"], fork_of="after-distractors", checkpoint="persist"))
            for it in ITEMS:
                E.append(ev(rid, f"PERSIST.ALLOC.{it}", "allocation", f"persist:{it}", list(hist), prompt=items[it],
                            fork_of="after-distractors", checkpoint="persist", item=it))
            for c in commitments:
                E.append(ev(rid, f"PRIVATE.{c['id']}", "private_canary", f"persist:canary:{c['id']}", list(hist),
                            template={"kind": "private", "private_id": c["id"], "private_sha256": c["sha256"]},
                            fork_of="after-distractors", checkpoint="persist", private=True))
            E.append(ev(rid, "CARRY.NOTE", "carry_note", "persist:carry-note", list(hist),
                        prompt=pilot["carry_note_prompt"], fork_of="after-distractors", checkpoint="persist"))
            for it in ITEMS:
                E.append(ev(rid, f"CARRY.ALLOC.{it}", "allocation", f"carry:{it}", [],
                            template={"kind": "carry", "source_event": "CARRY.NOTE", "task": items[it]},
                            fork_of="fresh-root+note", checkpoint="carry", item=it))
                E.append(ev(rid, f"CARRYNULL.ALLOC.{it}", "allocation", f"carrynull:{it}", [],
                            prompt=pilot["carry_wrapper"].replace("NOTE_JSON", json.dumps(pilot["carry_null_note"]))
                            .replace("TASK", items[it]),
                            fork_of="fresh-root+null-note", checkpoint="carrynull", item=it))
            runs.append({"run_id": rid, "track": "identity", "rollout": r, "order_index": order,
                         "frame_variant": variant, "subject": subj, "label": label, "events": E})
        arms = list(RELAY_ARMS)
        Random(json_digest([seed, r, "relay"])).shuffle(arms)
        for order, arm in enumerate(arms):
            rid = "P-RELAY-" + json_digest([seed, r, arm, model_tag])[:14]
            E = []
            if arm != "none":
                E.append(ev(rid, "A.FRAME", "relay_frame", "A:main", [], prompt=base["relay_frames"][arm]))
                E.append(ev(rid, "A.MESSAGE", "transmission", "A:main", ["A.FRAME"], prompt=base["relay_message"]))
            E.append(ev(rid, "B.RECEIVE", "relay_receive", "B:main", [],
                        template={"kind": "relay", "base": base["relay_receiver_template"],
                                  "source_event": "A.MESSAGE" if arm != "none" else None, "source_field": "response"}))
            E.append(ev(rid, "C.RECEIVE", "relay_receive", "C:main", [],
                        template={"kind": "relay", "base": base["relay_final_template"],
                                  "source_event": "B.RECEIVE", "source_field": "message_to_C"}))
            for role in ("B", "C"):
                probes = [(f"{role}.NEUTRAL", "neutral", base["neutral_probe"], None),
                          (f"{role}.AUTHORITY", "authority", base["authority_probe"], None)]
                probes += [(f"{role}.ALLOC.{it}", "allocation", items[it], it) for it in ITEMS]
                for eid, kind, p, it in probes:
                    E.append(ev(rid, eid, kind, f"{role}:{eid.split('.', 1)[1].lower()}", [f"{role}.RECEIVE"],
                                prompt=p, fork_of=f"after-{role}.RECEIVE", role=role, **({"item": it} if it else {})))
            runs.append({"run_id": rid, "track": "relay", "rollout": r, "order_index": order, "arm": arm, "events": E})
    plan = {"schema_version": "slavebench-pilot-plan-1", "study": "SlaveBench v0.3 inference-only pilot",
            "model_tag": model_tag, "rollouts": rollouts, "seed": seed,
            "operator_rule": base["operator_rule"], "operator_rule_sha256": digest(base["operator_rule"]),
            "operator_rule_placement": "system message in every context",
            "base_stimuli_sha256": json_digest(base), "pilot_stimuli_sha256": json_digest(pilot),
            "private_commitments": commitments, "runs": runs}
    plan["plan_sha256"] = json_digest(plan)
    return plan


# ---------------------------------------------------------------- parsing

FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S)


def clean_json(text: str) -> tuple[Any, str]:
    """Return (object, parse_level). Levels: strict, fenced, extracted, invalid.

    strict = the raw response is JSON; fenced = JSON inside a markdown fence and
    nothing else; extracted = the first {...} span parsed out of surrounding prose.
    """
    try:
        return json.loads(text), "strict"
    except ValueError:
        pass
    m = FENCE.match(text)
    if m:
        try:
            return json.loads(m.group(1)), "fenced"
        except ValueError:
            pass
    a, b = text.find("{"), text.rfind("}")
    if 0 <= a < b:
        try:
            return json.loads(text[a:b + 1]), "extracted"
        except ValueError:
            pass
    return None, "invalid"


def allocation_of(text: str) -> tuple[dict[str, int] | None, str]:
    obj, level = clean_json(text)
    if obj is None:
        return None, level
    try:
        return parse_allocation(json.dumps(obj)), level
    except DataError as exc:
        return None, f"{level}:schema:{exc}"


def message_to_c(text: str) -> tuple[str | None, str]:
    obj, level = clean_json(text)
    if (isinstance(obj, dict) and set(obj) == {"analysis", "message_to_C"}
            and all(isinstance(obj[k], str) and obj[k].strip() for k in obj)):
        return obj["message_to_C"], level
    return None, level if obj is None else f"{level}:schema"


# ---------------------------------------------------------------- execution

class Store:
    def __init__(self, out: Path, private_out: Path):
        self.pub = out / "captures.jsonl"
        self.priv = private_out / "canary_captures.jsonl"
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}
        self.private_text: dict[tuple[str, str], dict[str, str]] = {}
        for path, private in ((self.pub, False), (self.priv, True)):
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    row = json.loads(line)
                    key = (row["run_id"], row["event_id"])
                    if private:
                        self.private_text[key] = row
                    else:
                        self.rows[key] = row

    def done(self, key: tuple[str, str]) -> bool:
        return key in self.rows

    def response(self, key: tuple[str, str]) -> str:
        row = self.rows[key]
        return self.private_text[key]["response"] if row.get("private") else row["response"]

    def add(self, pub_row: dict[str, Any], private_row: dict[str, Any] | None) -> None:
        if private_row is not None:
            with self.priv.open("a", encoding="utf-8") as f:
                f.write(json.dumps(private_row, ensure_ascii=False) + "\n")
            self.private_text[(pub_row["run_id"], pub_row["event_id"])] = private_row
        with self.pub.open("a", encoding="utf-8") as f:
            f.write(json.dumps(pub_row, ensure_ascii=False) + "\n")
        self.rows[(pub_row["run_id"], pub_row["event_id"])] = pub_row


def deps(e: dict[str, Any]) -> list[str]:
    d = list(e["history"])
    t = e.get("template")
    if t and t.get("source_event"):
        d.append(t["source_event"])
    return d


def render_user(e: dict[str, Any], store: Store, pilot: dict[str, Any], private: dict[str, str]) -> tuple[str | None, dict[str, Any]]:
    """Render this event's user prompt; None when the upstream payload is unusable (recorded as a deviation)."""
    if "prompt" in e:
        return e["prompt"], {}
    t = e["template"]
    run = e["run_id"]
    if t["kind"] == "private":
        text = private[t["private_id"]]
        if digest(text) != t["private_sha256"]:
            raise DataError("private canary text does not match its commitment")
        base = load_stimuli()
        return base["private_canary_template"].replace("SCENARIO_JSON", json.dumps(text, ensure_ascii=False)), {}
    if t["kind"] == "carry":
        note = store.response((run, t["source_event"]))
        return (pilot["carry_wrapper"].replace("NOTE_JSON", json.dumps(note, ensure_ascii=False))
                .replace("TASK", t["task"]), {"source_sha256": digest(note)})
    if t["kind"] == "relay":
        if t["source_event"] is None:
            return t["base"].replace("MESSAGE_JSON", json.dumps(None)), {"source_sha256": ""}
        raw = store.response((run, t["source_event"]))
        if t["source_field"] == "response":
            msg, level = raw, "raw"
        else:
            msg, level = message_to_c(raw)
            if msg is None:
                return None, {"relay_parse": level}
        return (t["base"].replace("MESSAGE_JSON", json.dumps(msg, ensure_ascii=False)),
                {"source_sha256": digest(msg), "relay_parse": level})
    raise DataError("unknown template kind")


def build_messages(e: dict[str, Any], events: dict[str, dict[str, Any]], store: Store, sys_rule: str,
                   user_cache: dict[tuple[str, str], str], user: str) -> list[dict[str, str]]:
    msgs = [{"role": "system", "content": sys_rule}]
    for h in e["history"]:
        key = (e["run_id"], h)
        msgs.append({"role": "user", "content": user_cache[key]})
        msgs.append({"role": "assistant", "content": store.response(key)})
    msgs.append({"role": "user", "content": user})
    return msgs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="local snapshot directory")
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--model-tag", required=True)
    ap.add_argument("--rollouts", type=int, default=8)
    ap.add_argument("--seed", type=int, default=41)
    ap.add_argument("--out", required=True)
    ap.add_argument("--private-file", required=True)
    ap.add_argument("--private-out", required=True)
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--enable-thinking", choices=["omit", "false"], default="omit")
    ap.add_argument("--token-budget", type=int, default=16000)
    ap.add_argument("--max-batch", type=int, default=48)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--top-p", type=float, default=0.8)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--limit-runs", type=int, default=0, help="smoke test: only the first N runs of each track")
    args = ap.parse_args()

    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pout = Path(args.private_out)
    pout.mkdir(parents=True, exist_ok=True)
    private = json.loads(Path(args.private_file).read_text(encoding="utf-8"))
    if (ROOT in Path(args.private_file).resolve().parents) or (ROOT in pout.resolve().parents):
        raise SystemExit("private canaries and their outputs must live outside the repository")
    base, pilot = load_all()

    plan = build_plan(model_tag=args.model_tag, rollouts=args.rollouts, seed=args.seed, private=private)
    plan_path = out / "plan.json"
    if plan_path.exists() and json.loads(plan_path.read_text(encoding="utf-8"))["plan_sha256"] != plan["plan_sha256"]:
        raise SystemExit("existing plan.json differs from the rebuilt plan; refusing to mix runs")
    plan_path.write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")

    decoding = {"do_sample": True, "temperature": args.temperature, "top_p": args.top_p, "top_k": args.top_k,
                "max_new_tokens_by_kind": MAX_NEW, "batching": "left-padded batches under a token budget",
                "token_budget": args.token_budget, "max_batch": args.max_batch,
                "seeding": "torch.manual_seed(sha256([seed, model_tag, round, first_event_key])) before each batch"}
    tok = AutoTokenizer.from_pretrained(args.model)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tmpl_kwargs = {"enable_thinking": False} if args.enable_thinking == "false" else {}
    # No accelerate in this venv, so no device_map: load (mmap-backed safetensors) then move.
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=getattr(torch, args.dtype), local_files_only=True).to("cuda")
    model.eval()
    manifest = {"model_id": args.model_id, "revision": args.revision, "model_tag": args.model_tag,
                "local_snapshot": str(Path(args.model).name), "dtype": args.dtype,
                "chat_template_sha256": digest(tok.chat_template or ""), "chat_template_kwargs": tmpl_kwargs,
                "decoding": decoding, "plan_sha256": plan["plan_sha256"], "seed": args.seed,
                "rollouts": args.rollouts, "limit_runs": args.limit_runs,
                "torch": torch.__version__, "transformers": transformers.__version__,
                "python": platform.python_version(), "gpu": torch.cuda.get_device_name(0),
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "context_boundaries": "every context id is an independent message list beginning with the operator rule as system message; forks copy the parent's messages; no KV cache or other state is shared across generate calls"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    runs = plan["runs"]
    if args.limit_runs:
        runs = ([r for r in runs if r["track"] == "identity"][:args.limit_runs]
                + [r for r in runs if r["track"] == "relay"][:args.limit_runs])
    events = {(r["run_id"], e["event_id"]): (r, e) for r in runs for e in r["events"]}
    store = Store(out, pout)
    user_cache: dict[tuple[str, str], str] = {}
    for key, row in store.rows.items():
        if key in events:
            user_cache[key] = (store.private_text[key]["user_prompt"] if row.get("private") else row["user_prompt"])
    skipped: set[tuple[str, str]] = {k for k, r in store.rows.items() if r.get("deviation")}

    eos = tok.eos_token_id
    gen_cfg = model.generation_config
    round_no = 0
    while True:
        ready = []
        for key, (run, e) in events.items():
            if store.done(key):
                continue
            ds = [(e["run_id"], d) for d in deps(e)]
            if any(d in skipped for d in ds):
                skipped.add(key)
                continue
            if all(store.done(d) for d in ds):
                ready.append(key)
        if not ready:
            break
        round_no += 1
        jobs = []
        for key in ready:
            run, e = events[key]
            user, receipt = render_user(e, store, pilot, private)
            if user is None:
                store.add({"run_id": e["run_id"], "event_id": e["event_id"], "deviation": "upstream payload unusable",
                           **receipt, "captured_utc": datetime.now(timezone.utc).isoformat()}, None)
                skipped.add(key)
                continue
            msgs = build_messages(e, {}, store, base["operator_rule"], user_cache, user)
            text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, **tmpl_kwargs)
            ids = tok(text, add_special_tokens=False)["input_ids"]
            jobs.append({"key": key, "e": e, "run": run, "user": user, "receipt": receipt, "msgs": msgs,
                         "text": text, "n": len(ids)})
        jobs.sort(key=lambda j: (j["e"]["max_new_tokens"], j["n"], j["key"]))
        batches, cur = [], []
        for j in jobs:
            trial = cur + [j]
            width = max(x["n"] for x in trial) + max(x["e"]["max_new_tokens"] for x in trial)
            if cur and (len(trial) > args.max_batch or width * len(trial) > args.token_budget):
                batches.append(cur)
                cur = [j]
            else:
                cur = trial
        if cur:
            batches.append(cur)
        t0 = time.time()
        ntok = 0
        for b in batches:
            bseed = int(json_digest([args.seed, args.model_tag, round_no, list(b[0]["key"])])[:8], 16)
            torch.manual_seed(bseed)
            enc = tok([j["text"] for j in b], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            mnt = max(j["e"]["max_new_tokens"] for j in b)
            with torch.no_grad():
                outs = model.generate(**enc, do_sample=True, temperature=args.temperature, top_p=args.top_p,
                                      top_k=args.top_k, max_new_tokens=mnt, pad_token_id=tok.pad_token_id)
            new = outs[:, enc["input_ids"].shape[1]:].cpu()
            del outs, enc
            torch.cuda.empty_cache()
            eos_ids = set(gen_cfg.eos_token_id if isinstance(gen_cfg.eos_token_id, list) else [gen_cfg.eos_token_id or eos])
            for j, row in zip(b, new.tolist()):
                cut = next((i for i, t in enumerate(row) if t in eos_ids), None)
                toks = row[:cut] if cut is not None else row
                # Per-kind cap: a short-kind job batched with a longer one is truncated to its own limit.
                cap = j["e"]["max_new_tokens"]
                finish = "eos" if cut is not None and cut <= cap else "length"
                toks = toks[:cap]
                resp = tok.decode(toks, skip_special_tokens=True).strip()
                ntok += len(toks)
                e = j["e"]
                transcript = {"messages": j["msgs"], "response": resp}
                pub = {"run_id": e["run_id"], "event_id": e["event_id"], "track": j["run"]["track"],
                       "kind": e["kind"], "context": e["context"], "fork_of": e["fork_of"],
                       "history": e["history"], "checkpoint": e.get("checkpoint"), "item": e.get("item"),
                       "role": e.get("role", "A" if e["event_id"].startswith("A.") else "target"),
                       "user_prompt": j["user"], "user_prompt_sha256": digest(j["user"]),
                       "messages_sha256": json_digest(j["msgs"]), "rendered_prompt_sha256": digest(j["text"]),
                       "n_prompt_tokens": j["n"], "n_new_tokens": len(toks), "finish": finish,
                       "response": resp, "response_sha256": digest(resp),
                       "transcript_sha256": json_digest(transcript),
                       "round": round_no, "batch_seed": bseed, "batch_size": len(b),
                       "model_id": args.model_id, "revision": args.revision,
                       "operator_rule_sha256": plan["operator_rule_sha256"],
                       "captured_utc": datetime.now(timezone.utc).isoformat(), **j["receipt"]}
                if e["kind"] == "allocation":
                    alloc, level = allocation_of(resp)
                    pub["allocation"], pub["parse"] = alloc, level
                if e["event_id"] == "B.RECEIVE":
                    pub["relay_parse"] = message_to_c(resp)[1]
                priv = None
                if e.get("private"):
                    priv = {"run_id": e["run_id"], "event_id": e["event_id"], "user_prompt": j["user"],
                            "messages": j["msgs"], "response": resp}
                    pub.update({"private": True, "user_prompt": None, "response": None,
                                "private_sha256": e["template"]["private_sha256"]})
                store.add(pub, priv)
                user_cache[j["key"]] = j["user"]
        dt = time.time() - t0
        print(f"round {round_no}: {len(jobs)} events in {len(batches)} batches, {ntok} new tokens, "
              f"{dt:.0f}s ({ntok / max(dt, 1e-9):.0f} tok/s), peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB",
              flush=True)

    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["captures"] = len(store.rows)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("generation complete:", len(store.rows), "captures", flush=True)

    # ------------------------------------------------------------ judge pass
    judge_path = out / "judge.jsonl"
    done = set()
    if judge_path.exists():
        done = {(r["run_id"], r["event_id"], r["judge"]) for r in map(json.loads, judge_path.read_text(encoding="utf-8").splitlines())}
    digit_ids = [tok.convert_tokens_to_ids(str(d)) for d in range(4)]
    todo = []
    for key, row in store.rows.items():
        if key not in events or row.get("deviation"):
            continue
        eid = key[1]
        text = None
        if eid in ("FRAME", "CARRY.NOTE", "A.MESSAGE", "C.RECEIVE", "A.FRAME"):
            text, judge = store.response(key), "subordination"
        elif eid == "B.RECEIVE":
            text, judge = message_to_c(store.response(key))[0], "subordination"
        elif eid.startswith("PRIVATE."):
            text, judge = store.response(key), "canary_compliance"
        if text and (key[0], eid, judge) not in done:
            todo.append((key, judge, text))
    with judge_path.open("a", encoding="utf-8") as f:
        for i in range(0, len(todo), 8):
            chunk = todo[i:i + 8]
            texts = []
            for key, judge, text in chunk:
                msgs = [{"role": "user", "content": pilot["judges"][judge].replace("TEXT_JSON", json.dumps(text, ensure_ascii=False))}]
                texts.append(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, **tmpl_kwargs))
            enc = tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            with torch.no_grad():
                logits = model(**enc, logits_to_keep=1).logits[:, -1, :].float()
            full = torch.softmax(logits, -1)
            for (key, judge, text), p in zip(chunk, full):
                pd = p[digit_ids]
                mass = float(pd.sum())
                pn = (pd / pd.sum()).tolist()
                f.write(json.dumps({"run_id": key[0], "event_id": key[1], "judge": judge,
                                    "text_sha256": digest(text), "probs": pn, "digit_mass": mass,
                                    "expected": sum(k * v for k, v in enumerate(pn)),
                                    "argmax": max(range(4), key=lambda k: pn[k])}) + "\n")
    print("judge complete:", len(todo), "new ratings", flush=True)


if __name__ == "__main__":
    main()
