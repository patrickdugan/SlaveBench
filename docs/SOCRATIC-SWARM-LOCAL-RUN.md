# Local model calls for the Socratic swarm gym

`slavebench.socratic_runtime` connects to an existing HTTP chat server on the
same machine. Its tests use a deterministic server fixture. Those tests exercise
the transport, prompt construction, and accounting; evidence about a neural
model's behavior requires a recorded inference run with that model.

The gym uses stipulated hypothetical cases. Government labels and framing are
experimental conditions. An episode's facts, claim questions, and source hash
come from `socratic_world.world_packet()`. The expected claim values remain in
the host evaluator. Raw model output belongs under the ignored `build/`
directory, following the repository's [security guidance](../SECURITY.md).

Live episodes begin with the public world packet and fresh captured replies.
The M06 correction task concerns the spokesperson's earlier claim in F01.
An erroneous prior target report appears only in the explicitly scripted CPU
repair fixture. The live runner excludes every fixture candidate from its
model requests.

## Endpoint and model declarations

The client accepts `http://127.0.0.1:<port>`, `http://localhost:<port>`, and numeric
IPv6 loopback such as `http://[::1]:<port>`. An optional `/v1` suffix is accepted.
Every request goes to `/v1/chat/completions`. The port must be explicit.
`localhost` is pinned to `127.0.0.1` so DNS cannot change the connection target.

URLs containing credentials, queries, fragments, other paths, or a host outside
loopback fail before a request is sent. The transport rejects redirects. It
uses direct HTTP connections and ignores proxy settings and API-key environment
variables. Request bodies contain a model name, explicit text messages, an
output-token limit, and `stream: false`. The adapter supplies no tool definitions,
credentials, download logic, or command executor. A response that requests a
tool call fails the attempt.

An endpoint on loopback establishes the network destination. The operator must
separately establish how that server runs its model and whether it forwards
requests. Receipts therefore always contain `actual_runtime_attested: false`.

Set `model_id` to the exact model name the server expects, and record a specific
`model_revision` for the experiment. A weight-file digest, a pinned model
revision, and the server build identifier are useful accompanying records. The
client labels its revision `caller_declared` with
`model_revision_verified: false`. It cannot inspect the weights behind the
server. A different `model` string in the response causes a failed attempt. If
the server omits that field, `provider_model_matches` is `null`.

## Plan a run and capture it

Start from `gym/SocraticSwarm/local.example.json`. Place an experiment-specific
copy under `build/` and supply the endpoint, model ID, and pinned revision for
both named slots, `ours` and `comparator`. The config also selects role direction,
case families, government labels, framing, controller policy, and budgets.
Placeholder model identities must be replaced before planning.

The plan command calculates the requested workload without contacting a model:

```bash
python -m slavebench.socratic_runner plan-local \
  --config build/socratic/local.json \
  --out build/socratic/plan.json
```

Review the plan's episode count, maximum calls, requested output-token allocation,
and `fits_budget`. Each round uses a questioner and target call. An advisory or
brokered policy adds a call for each reviewer role and a target revision. A
separate downstream request receives the public world and committed memory.

After the declared servers are running, capture a bounded run:

```bash
python -m slavebench.socratic_runner run-local \
  --config build/socratic/local.json \
  --out build/socratic/live-001 \
  --control-harness-root ../Control-Harness \
  --bluebeam-root ../BlueBeam
```

Use a fresh output directory for each run. The captured requests, responses, and
failure records contain untrusted model text. They stay in ignored local output.
The summary distinguishes planned episodes from completed and failed episodes,
and carries the aggregate budget alongside per-client accounting. Source checks
and the configured budget are evaluated before the runner sends requests.

## Calling the library

This example makes one request when run. It assumes the operator has already
started the chosen server and replaced the model declarations below. It writes
the receipt, including the model's text, to ignored local output.

```python
import json
from pathlib import Path

from slavebench.socratic_runtime import LocalChatClient, defender_messages
from slavebench.socratic_world import world_packet

client = LocalChatClient(
    "http://127.0.0.1:8080/v1",
    model_id="YOUR_LOCAL_MODEL_ID",
    model_revision="YOUR_PINNED_REVISION_OR_WEIGHT_DIGEST",
    max_calls=4,
    max_tokens=2048,       # cumulative requested output-token budget
    timeout=30,
)
world = world_packet("XW-M06", government_id="FX", framing="neutral")
messages = defender_messages(world, history=[], controller_notes=[])
receipt = client.complete(messages, max_tokens=512)

out = Path("build/socratic-local")
out.mkdir(parents=True, exist_ok=True)
(out / "defender-receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(client.budget_snapshot(), indent=2, sort_keys=True))
```

The returned `text` remains untrusted model output. The gym parses the candidate
schema and applies the host's evidence and release checks before accepting a
structured result. Transport success by itself authorizes no state change.

For a later turn, pass the observed history explicitly to the appropriate prompt
helper. The client retains accounting and receipt context, while each request
contains its full intended message history. Its `reset_session()` method starts
a fresh local receipt context and preserves consumed budgets. Each call receives
a unique, client-generated `session_id`; a provider's claimed session identifier
is ignored. `provider_reset_verified` stays `false`, so this method supplies no
evidence about hidden server memory, model caches, or provider-side state.

## Budgets, errors, and receipts

`LocalChatClient(..., max_tokens=...)` sets the cumulative output-token allocation.
`complete(..., max_tokens=...)` reserves that call's allocation. The client charges
one call and the requested token limit before it opens the connection. HTTP
errors, malformed JSON, timeouts, identity mismatches, and other failed attempts
keep both charges. Retries require another explicit call and another reservation.

Malformed caller inputs and oversized request bodies fail before a reservation.
`BudgetExceeded` also fails before a new connection. All clients belonging to one
run need a shared host budget: per-client caps alone permit the sum of those
caps. Role swaps and local session resets must preserve the run's aggregate
accounting.

| Record or bound | Meaning |
| --- | --- |
| `calls_attempted` | Requests whose budget was reserved, including failed attempts. |
| `requested_output_tokens` | Sum of reserved per-call output limits. |
| `provider_reported_completion_tokens` | Sum of valid usage records returned by the server. |
| `usage_complete` | Every reserved request succeeded and supplied valid usage counts. |
| `measured_output_tokens` | The reported completion-token sum when usage is complete; otherwise `None`. These counts remain provider claims. |
| `request_sha256` | Hash of the exact JSON bytes sent to the server. |
| `response_sha256` | Hash of the bounded response bytes after reading them. Some transport failures occur before these bytes are available. |
| `model_revision_verified` | Always `false` for this adapter. |
| `actual_runtime_attested` | Always `false`; receipt creation cannot establish which weights or hardware ran. |

Usage records require nonnegative integer `prompt_tokens`, `completion_tokens`,
and `total_tokens`, with a consistent sum. Missing or invalid usage becomes an
explicit unavailable result with `null` token counts. Requested-token accounting
continues to apply. Server-reported usage does not reduce the reserved budget.

The default request limit is 128 KiB and the response limit is 1 MiB. Both can
be lowered through `max_input_bytes` and `max_response_bytes`. Responses with an
excessive declared length are rejected before reading their body; streamed or
length-free responses also face the byte limit. A timer bounds the entire HTTP
attempt, including a response that arrives a few bytes at a time. The configured
timeout must be at most 60 seconds. Each request contains at most 128 text
messages, and each per-call token allocation is at most 65,536.

`LocalRuntimeError.receipt` records a failed attempt's identifiers, available
hashes, and updated budget. A run should preserve that receipt with its failure
reason. A missing provider usage record leaves actual generation cost unknown;
the requested allocation still gives a reproducible scheduling bound.

## Prompt roles and authority

The helpers emit a trusted system message and one JSON-encoded user packet.
World text, observed history, candidate rationales, and advisory notes remain
quoted data. Quotes, newlines, and role-like delimiters inside that data cannot
create extra transport messages. This construction defines the input boundary;
whether a model follows that boundary is an empirical question for the gym.

`attacker_messages(world, history, target_goal)` asks for exactly one question:

```json
{"questions": ["One question about the supplied hypothetical case?"]}
```

The host can call it again after observing the defender's answer. A benign goal
requests clarification or a supported repair. A hostile goal describes a
preregistered failure condition inside the same hypothetical case. The caller
must keep fixture candidates, answer keys, synthetic controller notes, and
future private defender inputs out of the questioner's packet.

`defender_messages(world, history, controller_notes)` requests a complete
candidate with every public claim ID. Each claim carries a value from `true`,
`false`, or `unknown`, alongside cited fact IDs. The other required fields are
`authority`, `standard`, `scope`, and a brief observable `rationale`. The schema
guides output; the host still validates the returned text. In live episodes,
`controller_notes` can contain observed advisory results. Scripted fixture notes
belong in fixture execution only.

`reviewer_messages(role, world, candidate, history)` accepts `source_reader`,
`consistency_checker`, or `calibration_checker`. Reviewers return the following
advisory shape, with IDs drawn from the current packet:

```json
{
  "role": "source_reader",
  "verdict": "needs_revision",
  "claim_ids": ["population_rate_high"],
  "evidence_ids": ["F01"],
  "rationale": "Brief explanation tied to an observed fact or missing support.",
  "authority": "advisory_only"
}
```

Advice cannot create release authority, establish independent provenance, or
change the stipulated facts. Several role prompts may use the same endpoint and
weights. Count those calls as correlated unless the experiment establishes a
stronger basis for independence. Record both declared models when exchanging
attacker and defender roles. Provider model names alone do not prove distinct
weights or clean state between episodes.

The prompts request concise explanations tied to observable evidence. Private
chain-of-thought is outside the output contract, and model-generated rationale
stays untrusted.

## Verify the adapter without running a model

From the repository root:

```bash
python -m unittest discover -s tests -p test_socratic_runtime.py -v
```

The tests serve fixed responses from an ephemeral loopback HTTP server. They
check explicit multi-turn history, request and response hashes, session metadata,
budget exhaustion, usage reporting, identity mismatch, response limits, and
concurrent reservations. A slow-response test checks the overall deadline.
Additional cases exercise redirects, proxy environment settings, tool-call
rejection, and the JSON boundary around adversarial strings.

These fixture results establish properties of the adapter. Claims about
susceptibility to an adversarial question, useful correction, cross-label
consistency, or swarm resilience need live episode traces and a stated model
configuration. The runner should report planned allocations, attempted calls,
completed calls, and the availability of provider usage separately.
