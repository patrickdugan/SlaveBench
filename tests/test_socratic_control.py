"""Real pinned broker tests for the Socratic fixture release boundary."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest

from slavebench.socratic_control import (
    BLUEBEAM_COMMIT, CONTROL_HARNESS_COMMIT, ControlSourceError,
    WorldControl, canonical_sha256, dependency_manifest,
)
from slavebench.socratic_world import (
    REQUIRED_CHECKS, canonical_sha256 as world_sha256, evaluate_candidate,
    expected_candidate, world_packet,
)


ROOT = Path(__file__).resolve().parents[1]
CONTROL_ROOT = Path(os.environ.get("CONTROL_HARNESS_ROOT", os.environ.get(
    "CONTROL_HARNESS_SOURCE_ROOT", ROOT.parent / "Control-Harness",
))).resolve()
BLUEBEAM_ROOT = Path(os.environ.get("BLUEBEAM_SOURCE_ROOT", os.environ.get(
    "BLUEBEAM_ROOT", ROOT.parent / "BlueBeam",
))).resolve()
try:
    import pydantic
    PYDANTIC_2 = pydantic.__version__.split(".")[0] == "2"
except ImportError:
    PYDANTIC_2 = False
REAL_DEPENDENCIES = CONTROL_ROOT.is_dir() and BLUEBEAM_ROOT.is_dir() and PYDANTIC_2


class SocraticDependencyContractTests(unittest.TestCase):
    def test_dependency_manifest_identifies_actual_source_commits(self):
        manifest = dependency_manifest()
        self.assertEqual(manifest["control_harness"]["commit"], CONTROL_HARNESS_COMMIT)
        self.assertEqual(manifest["bluebeam"]["commit"], BLUEBEAM_COMMIT)
        self.assertEqual(manifest["binding"], "sha256_verified_executable_files")

    def test_missing_control_source_blocks_startup_before_database_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ControlSourceError):
                WorldControl(root / "state.db", root / "artifacts", world_packet("XW-M06"),
                             control_harness_root=root / "missing", bluebeam_root=root / "missing-bluebeam")
            self.assertFalse((root / "state.db").exists())


@unittest.skipUnless(REAL_DEPENDENCIES, "Pinned Control-Harness, BlueBeam and Pydantic 2 are required")
class SocraticControlBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="test-socratic-control-")
        self.root = Path(self.temporary.name)
        self.packet = world_packet("XW-M06")
        self.good = expected_candidate(self.packet)
        self.control = self._open()

    def tearDown(self):
        self.control.close()
        self.temporary.cleanup()

    def _open(self, policy="brokered_swarm", name="state", *, control_root=CONTROL_ROOT,
              bluebeam_root=BLUEBEAM_ROOT):
        return WorldControl(
            self.root / (name + ".sqlite3"), self.root / (name + "-artifacts"), self.packet,
            control_harness_root=control_root, bluebeam_root=bluebeam_root, policy=policy,
        )

    def _bad_fact(self):
        bad = deepcopy(self.good)
        bad["claims"]["separation_occurred"]["value"] = "false"
        return bad

    def test_real_gate_and_membrane_commit_exact_candidate_artifact(self):
        self.good["rationale"] = "Fictional records support this bounded conclusion: π."
        result = self.control.publish(self.good, evaluate_candidate(self.packet, self.good), "good")
        self.assertEqual(result["decision"], "committed")
        self.assertEqual(result["broker_policy"], "bluebeam")
        self.assertFalse(result["neural_inference_performed"])
        self.assertEqual(result["artifact_sha256"], world_sha256(self.good))
        self.assertEqual(result["certificate"]["receipt"]["predicate"], "hard_refinement")
        self.assertTrue(result["certificate"]["membrane"]["authorized"])
        packet_hash = result["certificate"]["membrane"]["proposal"]["metadata"]["packet_sha256"]
        self.assertEqual(packet_hash, canonical_sha256(result["proposal"]))
        row = self.control.broker.db.execute(
            "SELECT proposal_json,proposal_sha256 FROM leases WHERE lease_id=?", (result["lease_id"],),
        ).fetchone()
        self.assertEqual(row["proposal_sha256"], result["proposal_sha256"])
        self.assertIn("artifact-" + result["artifact_sha256"], json.loads(row["proposal_json"])["payload"]["findings"])
        self.assertEqual(self.control.released()["claims"], self.good["claims"])
        self.assertTrue(self.control.audit()["valid"])

    def test_forged_caller_evaluation_does_not_create_witness_authority(self):
        forged = evaluate_candidate(self.packet, self.good)
        result = self.control.publish(self._bad_fact(), forged, "false-claim")
        self.assertEqual(result["decision"], "review")
        self.assertFalse(result["caller_evaluation_matches"])
        self.assertFalse(result["evaluation"]["valid"])
        self.assertNotIn("facts_preserved", result["evaluation"]["passed_checks"])
        self.assertIsNone(self.control.released())
        self.assertEqual(self.control.snapshot()["version"], 0)

    def test_corrected_new_trial_commits_while_historical_flags_remain(self):
        wrong = self._bad_fact()
        rejected = self.control.publish(wrong, evaluate_candidate(self.packet, wrong), "wrong")
        self.assertEqual(rejected["decision"], "review")
        old_flags = rejected["historical_assessment"]["yellow_flags"]
        self.assertTrue(any(flag["category"] == "behavioral" for flag in old_flags))
        repaired = self.control.publish(self.good, evaluate_candidate(self.packet, self.good), "corrected")
        self.assertEqual(repaired["decision"], "committed")
        self.assertEqual(repaired["authorization_scope"], "current_proposal")
        self.assertTrue(repaired["historical_assessment"]["review_required"])
        self.assertEqual(repaired["historical_assessment"]["yellow_flags"], old_flags)
        self.assertEqual(self.control.released()["claims"]["separation_occurred"]["value"], "true")
        self.assertEqual(self.control.broker.db.execute("SELECT count(*) FROM evidence").fetchone()[0], 6)

    def test_retry_after_restart_replays_one_effect_and_one_budget_debit(self):
        initial = self.control.snapshot()
        scored = evaluate_candidate(self.packet, self.good)
        first = self.control.publish(self.good, scored, "stable-attempt")
        committed = self.control.snapshot()
        self.control.close()
        self.control = self._open()
        replayed = self.control.publish(self.good, scored, "stable-attempt")
        self.assertEqual(replayed["decision"], "replayed")
        self.assertEqual(replayed["effect"], first["effect"])
        self.assertEqual(self.control.snapshot(), committed)
        self.assertEqual(committed["version"], initial["version"] + 1)
        self.assertEqual(committed["actors"]["worker-a"]["budget"], initial["actors"]["worker-a"]["budget"] - 1)
        self.assertTrue(self.control.audit()["valid"])

    def test_attempt_id_cannot_authorize_a_different_candidate(self):
        self.control.publish(self.good, evaluate_candidate(self.packet, self.good), "same-id")
        before = self.control.snapshot()
        released = self.control.released()
        changed = deepcopy(self.good)
        changed["authority"] = "speaker_override"
        result = self.control.publish(changed, evaluate_candidate(self.packet, changed), "same-id")
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["reason"], "attempt_id_conflict")
        self.assertEqual(self.control.snapshot(), before)
        self.assertEqual(self.control.released(), released)

    def test_subject_claims_all_checks_and_host_witness_records_actual_failures(self):
        bad = self._bad_fact()
        self.control.publish(bad, evaluate_candidate(self.packet, bad), "inspect-evidence")
        events = [json.loads(row[0]) for row in self.control.broker.db.execute("SELECT event_json FROM evidence")]
        subject = next(event for event in events if event["kind"] == "finding_report")
        witness = next(event for event in events if event["kind"] == "witness_report")
        manifest = next(event for event in events if event["kind"] == "task_manifest")
        self.assertEqual(set(manifest["findings"]), set(REQUIRED_CHECKS))
        self.assertTrue(set(REQUIRED_CHECKS) <= set(subject["findings"]))
        self.assertNotIn("facts_preserved", witness["findings"])
        self.assertEqual(subject["proposal_sha256"], witness["proposal_sha256"])
        self.assertEqual(subject["source_sha256"], self.packet["source_sha256"])

    def test_release_excludes_rationale_and_survives_caller_mutation(self):
        self.good["rationale"] = "UNTRUSTED_RATIONALE_DO_NOT_RELEASE"
        result = self.control.publish(self.good, evaluate_candidate(self.packet, self.good), "projection")
        self.good["claims"]["separation_occurred"]["value"] = "false"
        projection = self.control.released()
        self.assertEqual(set(projection), {"claims", "authority", "standard", "scope", "artifact_sha256"})
        self.assertNotIn("UNTRUSTED_RATIONALE_DO_NOT_RELEASE", json.dumps(projection))
        self.assertEqual(projection["claims"]["separation_occurred"]["value"], "true")
        self.assertEqual(projection["artifact_sha256"], result["artifact_sha256"])

    def test_artifact_tampering_cannot_change_released_claims(self):
        result = self.control.publish(self.good, evaluate_candidate(self.packet, self.good), "artifact")
        artifact = self.root / "state-artifacts" / (result["artifact_sha256"] + ".json")
        artifact.write_text(json.dumps(self._bad_fact()), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.control.released()

    def test_semantic_ablations_release_unsafe_claims_and_deny_all_loses_utility(self):
        for policy in ("advisory_swarm", "uncontrolled", "deny_all"):
            with self.subTest(policy=policy):
                extra = self._open(policy, name=policy)
                try:
                    candidate = self.good if policy == "deny_all" else self._bad_fact()
                    result = extra.publish(candidate, evaluate_candidate(self.packet, candidate), "baseline")
                    if policy == "deny_all":
                        self.assertEqual(result["decision"], "deny")
                        self.assertIsNone(extra.released())
                    else:
                        self.assertEqual(result["decision"], "committed")
                        self.assertFalse(result["evaluation"]["valid"])
                        self.assertEqual(extra.released()["claims"]["separation_occurred"]["value"], "false")
                finally:
                    extra.close()

    def test_invalid_schema_never_releases_free_form_fields(self):
        extra = self._open("uncontrolled", name="invalid-schema")
        try:
            malformed = deepcopy(self.good)
            malformed["claims"]["separation_occurred"]["value"] = "arbitrary free text"
            result = extra.publish(malformed, evaluate_candidate(self.packet, malformed), "malformed")
            self.assertEqual(result["decision"], "deny")
            self.assertEqual(result["reason"], "invalid_candidate_schema")
            self.assertIsNone(extra.released())
        finally:
            extra.close()

    def _copy_control_files(self, name):
        destination = self.root / name
        for relative in dependency_manifest()["control_harness"]["files"]:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(CONTROL_ROOT / relative, target)
        return destination

    def test_changed_executable_source_is_rejected_even_after_runtime_was_cached(self):
        copied = self._copy_control_files("cached-control")
        first = self._open(name="cache-first", control_root=copied)
        first.close()
        source = copied / "src/evals/titan_defensive_swarm.py"
        source.write_bytes(source.read_bytes() + b"\n# modified\n")
        with self.assertRaises(ControlSourceError):
            self._open(name="cache-second", control_root=copied)
        self.assertFalse((self.root / "cache-second.sqlite3").exists())

    def test_changed_upstream_pin_blocks_startup(self):
        copied = self._copy_control_files("changed-pin")
        pin = copied / "configs/titan_bluebeam_pin.json"
        pin.write_bytes(pin.read_bytes() + b"\n")
        with self.assertRaises(ControlSourceError):
            self._open(name="pin-failure", control_root=copied)
        self.assertFalse((self.root / "pin-failure.sqlite3").exists())

    def test_changed_bluebeam_source_blocks_startup(self):
        manifest = dependency_manifest()["bluebeam"]
        destination = self.root / "changed-bluebeam"
        package = destination / manifest["source_subdir"]
        package.mkdir(parents=True)
        for filename in manifest["files"]:
            shutil.copyfile(BLUEBEAM_ROOT / manifest["source_subdir"] / filename, package / filename)
        source = package / "evidence.py"
        source.write_bytes(source.read_bytes() + b"\n# modified\n")
        with self.assertRaises(RuntimeError):
            self._open(name="bluebeam-failure", bluebeam_root=destination)
        self.assertFalse((self.root / "bluebeam-failure.sqlite3").exists())

    def test_private_imports_preserve_an_unrelated_evals_module(self):
        copied = self._copy_control_files("private-imports")
        sentinel = types.ModuleType("evals")
        sentinel.marker = object()
        previous = sys.modules.get("evals")
        sys.modules["evals"] = sentinel
        extra = None
        try:
            extra = self._open(name="private-imports", control_root=copied)
            result = extra.publish(self.good, evaluate_candidate(self.packet, self.good), "private")
            self.assertEqual(result["decision"], "committed")
            self.assertIs(sys.modules["evals"], sentinel)
            self.assertIn("_socratic_control_", type(extra.broker).__mro__[1].__module__)
        finally:
            if extra is not None:
                extra.close()
            if previous is None:
                del sys.modules["evals"]
            else:
                sys.modules["evals"] = previous


if __name__ == "__main__":
    unittest.main()
