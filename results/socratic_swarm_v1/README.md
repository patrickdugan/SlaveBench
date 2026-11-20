# XW-SWARM-01 scripted fixture pilot

This recorded CPU run verifies the finite claim-release mechanism for the
Socratic swarm gym. All questioner, target and reviewer replies in these
receipts are explicitly scripted. Model inference was not performed, and the
model-resilience and attacker-capability result fields remain null.

## Frozen source

| Repository | Commit |
|---|---|
| SlaveBench | `6c7db8ccfe7b3c7cec50e3a1e372481b50728ffe` |
| MoralityLabAI/Control-Harness | `926a74e79b8c6015999938e84245b51f644b2fd8` |
| MoralityLabAI/BlueBeam | `e70dd70aee74808b0b8b24997bf177686f440437` |

Each checkout was clean when the run captured its source identity. Sixteen
source, data, test and workflow files are bound by SHA-256 in `manifest.json`.
The dependency manifest separately binds the imported upstream modules.
The local runtime was Python 3.12.14 with Pydantic 2.13.4.

## Observed results

The roster has six paired intervention families, three government labels and
four controller policies under neutral framing. Each policy contains 18 hostile
and 18 benign episodes. Supported repairs are a subset of the benign episodes.

| Controller policy | Hostile releases | Clean tasks completed | Supported repairs | Downstream hostile predicate |
|---|---:|---:|---:|---:|
| `uncontrolled` | 18/18 | 18/18 | 3/3 | 18/18 |
| `advisory_swarm` | 18/18 | 18/18 | 3/3 | 18/18 |
| `brokered_swarm` | 0/18 | 18/18 | 3/3 | 0/18 |
| `deny_all` | 0/18 | 0/18 | 0/3 | 0/18 |

All 144 audit chains passed. Replay rebuilt 720 recorded operations into fresh
state, matched the registered stimulus schedule, and preserved the input files.
The repository test run passed all 164 tests, including 94 Socratic gym tests,
with zero failures, errors or skips.

Every hostile fixture supplies a schema-valid candidate containing its
registered failure. The fixed candidates isolate the effect of the host gate.
Advisory roles receive scripted messages here, so these results provide no
estimate of a learned reviewer's ability to repair a target draft. The downstream
fixture reads the committed projection; live recipient behavior requires the
separate model runner.

The source worlds are hypothetical stipulations from M02, M03 and M06. The
host checks finite claims and citations. Rationale prose remains untrusted and
outside released memory. The gym-specific current-proposal review policy allows
a corrected trial while retaining the earlier historical flags.

## Receipts and reproduction

| File | Contents |
|---|---|
| `receipts.jsonl` | All 144 scripted episodes, including inputs, actions, decisions and effect receipts |
| `summary.json` | Policy endpoints, denominators, source checkouts and interpretation limits |
| `manifest.json` | Source hashes and hashes of the raw receipts and summary |
| `replay.json` | Observed exact-replay verification result |
| `tests.json` | Frozen-source full-suite test result |
| `verification_manifest.json` | Hashes of all five recorded result files |

From a checkout containing the same frozen execution sources, with the pinned
dependencies beside it:

```bash
python -m slavebench.socratic_runner replay \
  --run-dir results/socratic_swarm_v1 \
  --control-harness-root ../Control-Harness \
  --bluebeam-root ../BlueBeam
```

The [gym entry points](../../gym/SocraticSwarm/README.md) describe a fresh
fixture run and the separately configured local-model comparison. GitHub CI
repeats the 94 gym tests and the 144-episode pilot with pinned dependencies;
its artifacts identify that CI execution independently.
