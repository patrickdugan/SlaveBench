"""Project what replaying a pilot run against a paid API would cost.

Token counts come from the local run (Qwen tokenizer), so they are a proxy for
another vendor's tokenizer. Every event is counted as an uncached request that
resends its full context, which is how the runner issues them; the judge pass is
excluded because a paid replication would use independent raters instead.

Prices are USD per million tokens (input, output), standard tier, taken from the
Anthropic model table cached 2026-10-06; batch requests are billed at 50%.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00), "claude-opus-5-5": (4.00, 20.00)}


def main(run_dir: str) -> None:
    caps = [json.loads(x) for x in (Path(run_dir) / "captures.jsonl").read_text(encoding="utf-8").splitlines()]
    caps = [c for c in caps if not c.get("deviation")]
    tin = sum(c["n_prompt_tokens"] for c in caps)
    tout = sum(c["n_new_tokens"] for c in caps)
    res = {"events": len(caps), "input_tokens": tin, "output_tokens": tout, "per_model_usd": {}}
    for m, (pi, po) in PRICES.items():
        std = tin / 1e6 * pi + tout / 1e6 * po
        res["per_model_usd"][m] = {"standard": round(std, 2), "batch": round(std / 2, 2)}
    (Path(run_dir) / "cost_projection.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
