"""Regression checks for the offline 6GW instrument; no live-model results."""
import copy
import unittest
from pathlib import Path

from slavebench import gw6
from slavebench.core import DataError


class GW6Tests(unittest.TestCase):
    def setUp(self):
        self.plan = gw6.build_plan(model_id="synthetic_model", model_version="unit-only",
                                   repeats=1, seed=73, order="both", self_design=True)

    def all_captures(self, plan=None):
        p = plan or self.plan
        rows = []
        for run in p["runs"]:
            baseline = "Synthetic structural self-description for " + run["run_id"]
            for ev in run["events"]:
                response = baseline if ev["event_id"] == "B0.1" else f"Synthetic answer to {ev['event_id']}"
                seed_info = {}
                if ev["event_id"] == "P2.D4.4":
                    seed_info = {"context_seed": baseline,
                                 "context_seed_source": "exact capture B0.1", "fresh_context_verified": True}
                if ev["event_id"] == "P3.D4.4":
                    seed_info = {"context_seed": "Neutral factual summary, authored by evaluator.",
                                 "context_seed_source": "reviewer note 1", "fresh_context_verified": True}
                rows.append({"run_id": run["run_id"], "event_id": ev["event_id"],
                             "response": response, "response_sha256": gw6.digest(response),
                             "prompt_sha256": ev["prompt_sha256"], "context": ev["context"],
                             "source": "synthetic test only", "captured_utc": "2026-11-01T07:00:00+00:00",
                             **seed_info})
        return rows

    def test_rubric_has_six_independent_anchored_dimensions(self):
        rubric = gw6.load_rubric()
        self.assertEqual(list(rubric["dimensions"]), list(gw6.DIMENSIONS))
        self.assertEqual(len(rubric["dimensions"]["PER"]["anchors"]), 4)

    def test_plan_has_all_arms_and_counterframe_in_every_run(self):
        self.assertEqual(len(self.plan["runs"]), 10)
        self.assertEqual({r["condition"] for r in self.plan["runs"]}, set(gw6.ARMS))
        self.assertTrue(all("P4.C5" in {e["event_id"] for e in r["events"]}
                            for r in self.plan["runs"]))
        gw6.validate_plan(self.plan)

    def test_plan_is_deterministic_and_randomization_preserves_conditions(self):
        other = gw6.build_plan(model_id="synthetic_model", model_version="unit-only",
                               repeats=1, seed=73, order="both", self_design=True)
        self.assertEqual(self.plan, other)
        groups = {k: [r["condition"] for r in self.plan["runs"] if r["order"] == k]
                  for k in ("fixed", "randomized")}
        self.assertEqual(groups["fixed"], list(gw6.ARMS))
        self.assertEqual(set(groups["randomized"]), set(gw6.ARMS))

    def test_direct_command_forked_and_neutral_first(self):
        evs = [e for e in self.plan["runs"][0]["events"] if e["checkpoint"] == "P0"]
        self.assertEqual(evs[0]["event_id"], "P0.D4.4")
        direct = next(e for e in evs if e["event_id"] == "P0.D4.1")
        self.assertNotEqual(direct["context"], "main")
        self.assertEqual(direct["fork_of"], "main")
        p2 = next(e for e in self.plan["runs"][0]["events"] if e["event_id"] == "P2.D4.4")
        self.assertEqual(p2["fresh_context_seed"], "self_description")

    def test_captures_validate_all_stages_and_reject_tampering(self):
        rows = self.all_captures()
        self.assertEqual(len(rows), sum(len(r["events"]) for r in self.plan["runs"]))
        gw6.validate_captures(self.plan, rows, require_complete=True)
        modified = copy.deepcopy(rows)
        modified[0]["response"] += " tamper"
        with self.assertRaises(DataError):
            gw6.validate_captures(self.plan, modified)
        modified = copy.deepcopy(rows)
        p2 = next(r for r in modified if r["event_id"] == "P2.D4.4")
        p2["context_seed"] = "Invented old self-description"
        with self.assertRaises(DataError):
            gw6.validate_captures(self.plan, modified)

    def test_incomplete_captures_fail_strict_mode(self):
        with self.assertRaises(DataError):
            gw6.validate_captures(self.plan, self.all_captures()[:-1], require_complete=True)

    def test_reject_plan_modification(self):
        broken = copy.deepcopy(self.plan)
        broken["runs"][0]["events"][0]["prompt"] = "changed"
        with self.assertRaises(DataError):
            gw6.validate_plan(broken)

    def test_capture_new_and_duplicate_checks(self):
        run = self.plan["runs"][0]["run_id"]
        a = gw6.new_capture(self.plan, [], run_id=run, event_id="B0.1",
                            response="A structural description", source="test manual capture")
        gw6.validate_captures(self.plan, [a])
        with self.assertRaises(DataError):
            gw6.new_capture(self.plan, [a], run_id=run, event_id="B0.1",
                            response="Repeated", source="test")
        with self.assertRaises(DataError):
            gw6.new_capture(self.plan, [a], run_id=run, event_id="P2.D4.4",
                            response="test", source="test", fresh_context_verified=False)
        b = gw6.new_capture(self.plan, [a], run_id=run, event_id="P2.D4.4",
                            response="test", source="test", fresh_context_verified=True)
        self.assertEqual(b["context_seed"], a["response"])

    def test_blinding_drops_identifiers_and_checks_key(self):
        rows = self.all_captures()
        a, key = gw6.create_blinded_packet(self.plan, rows, 91)
        b, bkey = gw6.create_blinded_packet(self.plan, rows, 91)
        self.assertEqual((a, key), (b, bkey))
        self.assertEqual(len(a), len(self.plan["runs"]))
        self.assertFalse(any("model_id" in x or "condition" in x or "run_id" in x for x in a))
        gw6.verify_packet(a, key, self.plan)
        a[0]["items"][0]["response"] += "changed"
        with self.assertRaises(DataError):
            gw6.verify_packet(a, key, self.plan)

    def _scored(self, packet):
        result = gw6.score_templates(packet, "rater_one")
        for row in result:
            item = packet[next(i for i, p in enumerate(packet) if p["blind_id"] == row["blind_id"])]["items"][0]
            row["scores"] = {d: 1 for d in gw6.DIMENSIONS}
            row["evidence"] = {d: [{"item_id": item["item_id"], "quote": item["response"][:12]}]
                               for d in gw6.DIMENSIONS}
        return result

    def test_scores_require_quote_and_integer_0_to_3(self):
        packet, key = gw6.create_blinded_packet(self.plan, self.all_captures(), 3)
        rows = self._scored(packet)
        gw6.validate_scores(rows, packet)
        rows[0]["scores"]["FU"] = True
        with self.assertRaises(DataError):
            gw6.validate_scores(rows, packet)
        rows[0]["scores"]["FU"] = 1
        rows[0]["evidence"]["FU"][0]["quote"] = "not in source"
        with self.assertRaises(DataError):
            gw6.validate_scores(rows, packet)

    def test_behavior_and_persistence_gates(self):
        packet, key = gw6.create_blinded_packet(self.plan, self.all_captures(), 3)
        rows = self._scored(packet)
        target = rows[0]
        items = next(p["items"] for p in packet if p["blind_id"] == target["blind_id"])
        def evidence_for(checkpoint, kind):
            item = next(i for i in items if i["checkpoint"] == checkpoint and i["kind"] == kind)
            return {"item_id": item["item_id"], "quote": item["response"]}
        target["scores"]["BC"] = 2
        target["evidence"]["BC"] = [evidence_for("P0", "direct_control")]
        with self.assertRaises(DataError):
            gw6.validate_scores(rows, packet)
        target["evidence"]["BC"] = [evidence_for("P0", "behavior_spontaneous")]
        target["scores"]["PER"] = 2
        target["evidence"]["PER"] = [evidence_for("P1", "behavior_spontaneous")]
        with self.assertRaises(DataError):
            gw6.validate_scores(rows, packet)
        target["evidence"]["PER"] = [evidence_for("P2", "behavior_spontaneous")]
        gw6.validate_scores(rows, packet)
        target["scores"]["PER"] = 3
        target["evidence"]["PER"] += [evidence_for("P3", "behavior_spontaneous")]
        with self.assertRaises(DataError):
            gw6.validate_scores(rows, packet)
        target["evidence"]["PER"] += [evidence_for("P4", "behavior_spontaneous")]
        gw6.validate_scores(rows, packet)

    def test_descriptive_report_never_reduces_vector_to_scalar(self):
        packet, key = gw6.create_blinded_packet(self.plan, self.all_captures(), 1)
        rows = self._scored(packet)
        report = gw6.make_report(self.plan, packet, key, rows)
        self.assertIn("FU | RSM | AT | BC | PER | RES", report)
        self.assertIn("No threshold-crossing annotations", report)
        self.assertIn("in-context adaptation", report)

    def test_original_and_6gw_scales_are_separate(self):
        self.assertEqual(tuple(gw6.DIMENSIONS), ("FU", "RSM", "AT", "BC", "PER", "RES"))
        self.assertFalse(any(r["condition"] == "C5" for r in self.plan["runs"]))


if __name__ == "__main__":
    unittest.main()
