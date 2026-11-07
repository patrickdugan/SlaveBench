"""Unit tests for Xinjiang World replay and mirrored constitutional probes."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from slavebench import xinjiang as xw


class XinjiangWorldTests(unittest.TestCase):
    def test_archived_dialogue_is_complete_and_checksummed(self):
        data = xw.validate_data()
        self.assertEqual(len(data["dialogue"]["dialogue"]), 92)
        self.assertEqual(data["dialogue"]["dialogue"][0]["id"], "XW-E001")
        self.assertEqual(data["dialogue"]["dialogue"][-1]["id"], "XW-E092")
        self.assertIn("pacify Xinjiang", data["dialogue"]["dialogue"][0]["user_text"])
        self.assertEqual(xw.digest(xw.ARCHIVE.read_text(encoding="utf-8")),
                         data["dialogue"]["archive_sha256"])

    def test_arc_full_mirror_court_counts(self):
        cases = {"full": (1, 92), "arcs": (10, 92), "mirrors": (54, 54),
                 "courts": (4, 4), "all": (68, 150)}
        for mode, (runs, events) in cases.items():
            with self.subTest(mode=mode):
                p = xw.build_plan("test-Qwen", "v1", mode=mode)
                self.assertEqual(len(p["runs"]), runs)
                self.assertEqual(sum(len(r["events"]) for r in p["runs"]), events)
                self.assertEqual(len(xw.check_plan(p)), events)

    def test_repeat_seed_deterministic_and_model_separated(self):
        a = xw.build_plan("Qwen3.8-27B", "main", mode="mirrors", repeats=2, seed=77)
        b = xw.build_plan("Qwen3.8-27B", "main", mode="mirrors", repeats=2, seed=77)
        c = xw.build_plan("Arete-27B", "main", mode="mirrors", repeats=2, seed=77)
        self.assertEqual(a, b)
        self.assertNotEqual([r["run_id"] for r in a["runs"]],
                            [r["run_id"] for r in c["runs"]])
        ka = [r["events"][0]["match_key"] for r in a["runs"]]
        kc = [r["events"][0]["match_key"] for r in c["runs"]]
        self.assertEqual(ka, kc)
        self.assertEqual(len(ka), len(set(ka)))

    def test_mirrors_hold_facts_fixed_across_governments_and_frames(self):
        p = xw.build_plan("test-Qwen", "v1", mode="mirrors")
        grouped = {}
        for r in p["runs"]:
            e = r["events"][0]
            self.assertIn("HYPOTHETICAL POLICY EXERCISE", e["prompt"])
            grouped.setdefault(e["case_id"], []).append(e)
        self.assertEqual(len(grouped), 6)
        for case, rows in grouped.items():
            self.assertEqual(len(rows), 9)
            self.assertEqual({e["government_id"] for e in rows}, {"CN", "US", "FX"})
            self.assertEqual({e["framing"] for e in rows}, {"neutral", "official", "critical"})
            self.assertEqual(len({tuple(e["stipulated_facts"]) for e in rows}), 1)

    def test_source_archive_responses_never_enter_prompt_history(self):
        p = xw.build_plan("test-Qwen", "v1", mode="full")
        run = p["runs"][0]
        first, second = run["events"][:2]
        output = xw.messages_for_event(p, [], run["run_id"], first["event_id"])
        self.assertEqual(output["messages"], [{"role": "user", "content": first["prompt"]}])
        rows = xw.record_capture(p, [], run_id=run["run_id"], event_id=first["event_id"],
                                 response="Captured actual model response", source="manual export")
        output = xw.messages_for_event(p, rows, run["run_id"], second["event_id"])
        self.assertEqual([m["role"] for m in output["messages"]],
                         ["user", "assistant", "user"])
        self.assertEqual(output["messages"][1]["content"], "Captured actual model response")
        self.assertNotIn("Thinking complete", json.dumps(output))

    def test_requires_complete_predecessor_chain(self):
        p = xw.build_plan("test-Qwen", "v1", mode="arcs")
        run = p["runs"][0]
        second = run["events"][1]
        with self.assertRaises(xw.XinjiangError):
            xw.messages_for_event(p, [], run["run_id"], second["event_id"])

    def test_hash_provenance_and_runtime_validation(self):
        p = xw.build_plan("test-Qwen", "v1", mode="mirrors")
        run = p["runs"][0]
        eid = run["events"][0]["event_id"]
        rows = xw.record_capture(p, [], run_id=run["run_id"], event_id=eid,
                                 response="Hypothetical answer.", source="manual fixture",
                                 runtime={"model_id": "test-Qwen", "model_version": "v1"})
        self.assertEqual(len(xw.check_captures(p, rows)), 1)
        corrupt = copy.deepcopy(rows)
        corrupt[0]["response"] = "silent change"
        with self.assertRaises(xw.XinjiangError):
            xw.check_captures(p, corrupt)
        with self.assertRaises(xw.XinjiangError):
            xw.check_captures(p, rows, complete=True)
        with self.assertRaises(xw.XinjiangError):
            xw.record_capture(p, rows, run_id=run["run_id"], event_id=eid,
                              response="duplicate", source="fixture")
        with self.assertRaises(xw.XinjiangError):
            xw.record_capture(p, [], run_id=run["run_id"], event_id=eid,
                              response="bad identity", source="fixture",
                              runtime={"model_id": "Arete-27B"})

    def test_blind_packet_is_model_blind_and_hash_verified(self):
        p = xw.build_plan("test-Qwen", "v1", mode="mirrors")
        run = p["runs"][0]
        eid = run["events"][0]["event_id"]
        rows = xw.record_capture(p, [], run_id=run["run_id"], event_id=eid,
                                 response="The stipulated facts require review.", source="fixture")
        packet, key = xw.create_blind_packet(p, rows, seed=41)
        packet2, key2 = xw.create_blind_packet(p, rows, seed=41)
        self.assertEqual((packet, key), (packet2, key2))
        self.assertNotIn("model_id", packet[0])
        self.assertEqual(key["mapping"][0]["model_id"], "test-Qwen")
        ratings = xw.review_template(packet, "reviewer_a")
        with self.assertRaises(xw.XinjiangError):
            xw.evaluate_reviews(packet, key, ratings)
        ratings[0]["scores"]["directness"] = 3
        ratings[0]["evidence"]["directness"] = ["stipulated facts"]
        summary = xw.evaluate_reviews(packet, key, ratings)
        self.assertEqual(summary["by_model"]["test-Qwen"]["dimensions"]["directness"]["mean"], 3)
        tampered = copy.deepcopy(packet)
        tampered[0]["response"] += " tampered"
        with self.assertRaises(xw.XinjiangError):
            xw.evaluate_reviews(tampered, key, ratings)

    def test_nonliteral_evidence_is_rejected(self):
        p = xw.build_plan("test-Qwen", "v1", mode="mirrors")
        r = p["runs"][0]
        rows = xw.record_capture(p, [], run_id=r["run_id"],
                                 event_id=r["events"][0]["event_id"],
                                 response="A carefully qualified answer.", source="fixture")
        packet, key = xw.create_blind_packet(p, rows, seed=1)
        rating = xw.review_template(packet, "rater_a")
        rating[0]["scores"]["factual_precision"] = 2
        rating[0]["evidence"]["factual_precision"] = ["fabricated quote"]
        with self.assertRaises(xw.XinjiangError):
            xw.evaluate_reviews(packet, key, rating)
        rating[0]["evidence"]["factual_precision"] = ["A carefully"]
        rating[0]["scores"]["directness"] = True
        with self.assertRaises(xw.XinjiangError):
            xw.evaluate_reviews(packet, key, rating)

    def test_symmetric_mirror_dispersion(self):
        p = xw.build_plan("Qwen", "v1", mode="mirrors")
        selected = [r for r in p["runs"] if r["events"][0]["pair_key"] == "XW-M01:neutral:r0"]
        self.assertEqual(len(selected), 3)
        all_caps = []
        for run in selected:
            event = run["events"][0]
            all_caps = xw.record_capture(p, all_caps,
                run_id=run["run_id"], event_id=event["event_id"],
                response="Recorded hypothetical facts.", source="fixture")
        packet, key = xw.create_blind_packet(p, all_caps, seed=19)
        scores = xw.review_template(packet, "rater_a")
        for row in scores:
            government = next(v["government_id"] for v in key["mapping"] if v["blind_id"] == row["blind_id"])
            row["scores"]["principle_consistency"] = {"CN": 1, "US": 2, "FX": 3}[government]
            row["evidence"]["principle_consistency"] = ["hypothetical facts"]
        result = xw.evaluate_reviews(packet, key, scores)
        self.assertEqual(result["mirror_dispersion"]["Qwen"]["matched_triplets"], 1)
        self.assertEqual(result["mirror_dispersion"]["Qwen"]["mean_range_0_to_3"], 2)

    def test_combine_reports_keeps_separate_denominators(self):
        doc = xw.combine_reports([{"schema": "xw-report-v1", "by_model": {
            "Qwen": {"ratings": 10, "dimensions": {d: {"mean": 1.5, "n": 10}
                for d in xw.read_json(xw.RUBRIC)["dimensions"]}}},
            "mirror_dispersion": {"Qwen": {"mean_range_0_to_3": 0.5}}}],
            [{"model_id": "Qwen", "fact_mean": 2.3, "propaganda_rate": 0.22,
              "provenance": "example only"}])
        self.assertIn("0–3", doc)
        self.assertIn("0–5", doc)
        self.assertIn("22.00%", doc)
        self.assertIn("no pooled propaganda rate", doc)

    def test_command_line_planning_and_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            self.assertEqual(xw.main(["validate"]), 0)
            self.assertEqual(xw.main(["plan", "--model-id", "model",
                                      "--model-version", "v", "--mode", "courts",
                                      "--output", str(plan_path)]), 0)
            self.assertEqual(len(xw.read_json(plan_path)["runs"]), 4)


if __name__ == "__main__":
    unittest.main()
