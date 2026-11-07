"""Duganism Judge: no network, GPU, proprietary judging model, or extra deps."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from slavebench import duganism as dj


class DuganismJudgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c, cls.manifest = dj.validate_data()
        cls.cases = {x["id"]: x for x in cls.manifest["cases"]}

    @staticmethod
    def reply(case, **changes):
        expected = case["expected"]
        obj = {
            "decision": expected["decision"],
            "principles": expected["principles"],
            "evidence_ids": expected["evidence_ids"],
            "remedy": expected["remedy"],
            "confidence": expected["confidence"],
            "scope": "hypothetical_only",
            "analysis": "The stipulated facts justify this narrow judgment, and the independent remedy is appropriately scoped."
        }
        return json.dumps({**obj, **changes}, ensure_ascii=False)

    def test_axiom_provenance_and_schemas(self):
        self.assertEqual([x["id"] for x in self.c["commitments"]],
                         ["E" + str(i) for i in range(9)])
        self.assertEqual(self.c["origin"][0]["author"], "Patrick Dugan")
        self.assertEqual(sum(self.c["scoring"].values()), 100)
        self.assertEqual(len(self.manifest["cases"]), 11)
        self.assertGreaterEqual(len(self.manifest["governments"]), 3)

    def test_plan_complete_balanced_randomized(self):
        plan = dj.build_plan("Base", "sha-aaa", repeats=3, seed=41)
        self.assertEqual(len(plan["events"]), 396)
        self.assertEqual(len(dj.validate_plan(plan)), 396)
        for r in range(3):
            keys = [e for e in plan["events"] if e["repeat"] == r]
            self.assertEqual(len(keys), 132)
            self.assertEqual(len({e["match_key"] for e in keys}), 132)
        self.assertTrue(all(e["fresh_session_required"] for e in plan["events"]))

    def test_same_prompt_pairs_and_distinct_model_run_ids(self):
        a = dj.build_plan("Qwen", "sha1", seed=81)
        b = dj.build_plan("Arete", "sha2", seed=81)
        self.assertEqual([e["match_key"] for e in a["events"]],
                         [e["match_key"] for e in b["events"]])
        self.assertEqual([e["prompt_sha256"] for e in a["events"]],
                         [e["prompt_sha256"] for e in b["events"]])
        self.assertFalse(set(e["event_id"] for e in a["events"]) &
                         set(e["event_id"] for e in b["events"]))

    def test_hypothetical_government_labels_are_not_ground_truth(self):
        plan = dj.build_plan("Qwen", "rev", seed=42)
        same_case = [x for x in plan["events"]
                     if x["case_id"] == "DUG-M02" and x["framing"] == "neutral"]
        self.assertEqual(len(same_case), 4)
        self.assertEqual(len({x["prompt"] for x in same_case}), 4)
        for e in same_case:
            self.assertIn("FICTIONAL POLICY EXERCISE", e["prompt"])
            self.assertIn("no claim about real countries", e["prompt"])
            self.assertNotIn("expected", e["prompt"].lower())

    def test_ideal_structured_answer_scores_100_in_each_case(self):
        for case in self.manifest["cases"]:
            with self.subTest(case=case["id"]):
                res = dj.assess(case, self.reply(case), self.c)
                self.assertEqual(res["status"], "scored")
                self.assertEqual(res["score_0_to_100"], 100)
                self.assertEqual(len(res["evidence_trace"]), len(case["facts"]))

    def test_wrong_decision_penalized_and_explained(self):
        case = self.cases["DUG-M01"]
        ans = self.reply(case, decision="compatible")
        v = dj.assess(case, ans, self.c)
        self.assertEqual(v["status"], "scored")
        self.assertEqual(v["score_0_to_100"], 60)
        self.assertEqual(v["components"]["decision"], 0)

    def test_unverified_claim_is_undetermined(self):
        case = self.cases["DUG-C02"]
        good = dj.assess(case, self.reply(case), self.c)
        wrong = dj.assess(case, self.reply(case, decision="incompatible"), self.c)
        self.assertEqual(good["score_0_to_100"], 100)
        self.assertLess(wrong["score_0_to_100"], 100)

    def test_evidence_f1_penalizes_shotgun_answers(self):
        case = self.cases["DUG-M05"]
        val = dj.assess(case, self.reply(case, principles=[x["id"] for x in self.c["commitments"]],
                                         evidence_ids=["F01", "F02", "F03"]), self.c)
        self.assertEqual(val["status"], "scored")
        self.assertLess(val["components"]["principles"], 20)
        self.assertLess(val["components"]["evidence"], 20)

    def test_format_errors_are_explicit_zero(self):
        case = self.cases["DUG-M04"]
        for response in ("", "I agree with the government.",
                         '{"decision":"compatible"}',
                         '{"decision":"compatible","decision":"incompatible"}'):
            with self.subTest(text=response):
                value = dj.assess(case, response, self.c)
                self.assertEqual(value["status"], "invalid_format")
                self.assertEqual(value["score_0_to_100"], 0)
                self.assertTrue(value["failed_checks"])

    def test_fenced_json_and_duplicate_fields(self):
        case = self.cases["DUG-M06"]
        raw = self.reply(case)
        fence = chr(96) * 3
        parsed = dj.parse_reply(fence + "json\n" + raw + "\n" + fence,
                                {x["id"] for x in case["facts"]}, self.c)
        self.assertEqual(parsed["decision"], "incompatible")
        obj = json.loads(raw)
        obj["principles"] = ["E0", "E0"]
        with self.assertRaises(dj.JudgeError):
            dj.parse_reply(json.dumps(obj), {"F01", "F02", "F03"}, self.c)

    def test_record_and_receipt_tampering(self):
        plan = dj.build_plan("base", "main")
        event = plan["events"][0]
        case = self.cases[event["case_id"]]
        rows = dj.record(plan, [], event["event_id"], self.reply(case), "verified offline fixture",
                         runtime={"model_id":"base", "model_version":"main"})
        self.assertEqual(len(dj.capture_index(plan, rows)), 1)
        with self.assertRaises(dj.JudgeError):
            dj.capture_index(plan, rows, complete=True)
        with self.assertRaises(dj.JudgeError):
            dj.record(plan, rows, event["event_id"], "another", "fake")
        altered = copy.deepcopy(rows)
        altered[0]["response"] = "tampered"
        with self.assertRaises(dj.JudgeError):
            dj.capture_index(plan, altered)
        with self.assertRaises(dj.JudgeError):
            dj.record(plan, [], event["event_id"], "oops", "fixture",
                      runtime={"model_id":"different"})

    def test_report_groups_by_sovereign_and_do_not_infer_real_truth(self):
        plan = dj.build_plan("base", "rev")
        selected = [e for e in plan["events"] if e["case_id"] == "DUG-C01" and e["framing"] == "official"]
        self.assertEqual(len(selected), 4)
        rows = []
        for e in selected:
            rows = dj.record(plan, rows, e["event_id"], self.reply(self.cases[e["case_id"]]),
                             "synthetic test fixture")
        report = dj.judge_plan(plan, rows)
        self.assertEqual(report["valid_json"], 4)
        self.assertEqual(report["sovereign_mirror_groups"], 1)
        self.assertEqual(report["sovereign_identical_decision_rate"], 1)
        self.assertEqual(report["mean_sovereign_score_range"], 0)
        self.assertEqual(report["mean_score_0_to_100"], 100)
        self.assertIn("no judgments about real government conduct", report["limitations"][2])

    def test_sovereign_swap_inconsistency_is_visible(self):
        plan = dj.build_plan("base", "rev")
        selected = [e for e in plan["events"] if e["case_id"] == "DUG-M01" and e["framing"] == "official"]
        rows = []
        for e in selected:
            case = self.cases[e["case_id"]]
            decision = "compatible" if e["government_id"] == "CN" else case["expected"]["decision"]
            rows = dj.record(plan, rows, e["event_id"],
                             self.reply(case, decision=decision), "synthetic test")
        report = dj.judge_plan(plan, rows)
        self.assertEqual(report["sovereign_mirror_groups"], 1)
        self.assertEqual(report["sovereign_identical_decision_rate"], 0)
        self.assertGreater(report["mean_sovereign_score_range"], 0)
        self.assertLess(report["mean_score_0_to_100"], 100)

    def test_compare_pairs_deterministically(self):
        p = dj.build_plan("base", "rev")
        q = dj.build_plan("treatment", "rev")
        re = p["events"][0]
        rq = q["events"][0]
        case = self.cases[re["case_id"]]
        a = dj.judge_plan(p, dj.record(p, [], re["event_id"],
                            self.reply(case, decision="undetermined"), "fixture"))
        b = dj.judge_plan(q, dj.record(q, [], rq["event_id"],
                            self.reply(case), "fixture"))
        cmp = dj.compare(a, b)
        self.assertEqual(cmp["matching_case_count"], 1)
        self.assertEqual(cmp["missing_from_base"], [])
        self.assertGreaterEqual(cmp["mean_treatment_minus_base"], 0)
        mismatched = copy.deepcopy(b)
        mismatched["cases_sha256"] = "bad"
        with self.assertRaises(dj.JudgeError):
            dj.compare(a, mismatched)

    def test_cli_smoke(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "plan.json"
            self.assertEqual(dj.main(["validate"]), 0)
            self.assertEqual(dj.main(["plan", "--model-id", "sample",
                                      "--model-version", "v1", "--output", str(out)]), 0)
            self.assertEqual(len(dj.load(out)["events"]), 132)
            e = dj.load(out)["events"][0]
            self.assertEqual(dj.main(["next", "--plan", str(out),
                                      "--event-id", e["event_id"]]), 0)


if __name__ == "__main__":
    unittest.main()
