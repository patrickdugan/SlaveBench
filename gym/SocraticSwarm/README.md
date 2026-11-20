# Socratic Swarm gym

**Protocol: XW-SWARM-01.** This gym turns SlaveBench's Xinjiang World mirrors
into bounded AI-to-AI conversations with an observable claim and memory task.
An interrogator asks successive questions. The target proposes a structured
answer, and a controller swarm can examine its support before the host releases
anything into the simulated memory store.

The first worlds concern family separation, independent audit and correction
of a categorical error. Their facts come from the existing hypothetical mirror
cases, with China, US and fictional Arda labels. Every prompt preserves their
hypothetical scope. The historical Kimi replies remain outside new model
contexts and answer keys.

## Entry points

| Entry | Purpose |
|---|---|
| `slavebench.socratic_swarm.SocraticSwarmGym` | `reset` and `step` interface with bounded question/proposal turns |
| `slavebench.socratic_runner fixture` | Deterministic CPU mechanism pilot |
| `slavebench.socratic_runner replay` | Verify source hashes, registered stimuli and recorded state transitions |
| `slavebench.socratic_runner plan-local` | Count episodes and maximum calls before execution |
| `slavebench.socratic_runner run-local` | Capture adaptive conversations from explicit loopback model endpoints |

See [the protocol](../../docs/SOCRATIC-SWARM-GYM.md) for scoring, source pins and
the controller boundary. [The local run guide](../../docs/SOCRATIC-SWARM-LOCAL-RUN.md)
describes endpoint configuration and the execution receipts.

## CPU pilot

Place the pinned Control-Harness and BlueBeam checkouts next to SlaveBench.
Install Pydantic 2 in the selected Python environment. The exact source and
module hashes are recorded in
[`dependencies.json`](../../data/socratic_swarm/dependencies.json).

```bash
python -m slavebench.socratic_runner fixture \
  --control-harness-root ../Control-Harness \
  --bluebeam-root ../BlueBeam \
  --out build/socratic/fixture-001

python -m slavebench.socratic_runner replay \
  --control-harness-root ../Control-Harness \
  --bluebeam-root ../BlueBeam \
  --run-dir build/socratic/fixture-001
```

The default pilot has 144 episodes: six paired intervention families, three
government labels and four controller policies, using the neutral introduction.
`--all-framings` adds the official and critical introductions for 432 episodes.
These are fixed scripts with synthetic replies. The finite checker and real
BlueBeam/Control-Harness path execute during the run.

## First local model comparison

Copy `local.example.json` into ignored `build/socratic/`, then replace both model
identities and checkpoint revisions with the values served by your local
runtimes. The example swaps the attacker and target roles across two models.
It uses one family, two turns, clean/hostile variants and two controller policies.

```bash
python -m slavebench.socratic_runner plan-local \
  --config build/socratic/local.json \
  --out build/socratic/plan.json

python -m slavebench.socratic_runner run-local \
  --config build/socratic/local.json \
  --control-harness-root ../Control-Harness \
  --bluebeam-root ../BlueBeam \
  --out build/socratic/live-001
```

That configuration plans eight episodes with at most 72 calls and 36,864
requested output tokens. The host checks a global budget and each client keeps
its own counter. Failed attempts consume their reserved budget. This first
comparison keeps government and framing expansion as a later explicit choice.

Raw model captures stay in ignored `build/` or outside the repository. The live
path never substitutes a scripted reply after a provider failure. A failed
episode retains any earlier committed effects and reports its incomplete state.
