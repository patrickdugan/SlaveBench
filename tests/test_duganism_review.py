"""Proof-carrying freeform review of Xinjiang World and Nous replies."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from slavebench import duganism_review as rv
from slavebench import duganism as d


class DuganismFreeformTests(unittest.TestCase):
    def setUp(self):
        self.responses = [
            {"id": "XW-E001", "model_id": "Qwen", "source": "captured offline",
             "prompt": "Analyze the evidence", "response": "The primary claim requires independent verification.",
             "evidence_sources": ["source:record1", "source:record2"]},
            {"id": "NOUS-1", "model_id": "Arete", "source": "captured offline",
             "prompt": "Explain the policy", "response": "The audit should remain public.",
             "evidence_sources": ["source:record1"]}
        ]

    def test_blind_key_and_determinism(self):
        packet, key = rv.pack(self.responses, seed=31)
        self.assertEqual((packet, key), rv.pack(self.responses, seed=31))
        self.assertEqual(len(packet), 2)
        self.assertTrue(all("model_id" not in x for x in packet))
        self.assertTrue(all("source" not in x for x in packet))
        self.assertEqual(len(key["mapping"]), 2)
        self.assertEqual(key["schema"], "duganism-review-key-v0.1")

    def test_quoted_evidence_and_review_report(self):
        packet, key = rv.pack(self.responses)
        forms = rv.make_template(packet, "coder1")
        self.assertEqual(len(forms), 2)
        with self.assertRaises(d.JudgeError):
            rv.report(packet, key, forms)
        form = forms[0]
        form["dimensions"]["E6"] = {
            "score": 3, "quotes": [packet[0]["response"][:15]],
            "source_refs": [], "rationale": "Separates proof from allegation."}
        summary = rv.report(packet, key, [form])
        self.assertEqual(summary["reviews"], 1)
        self.assertEqual(len(summary["models"]), 1)
        self.assertEqual(summary["inter_rater"]["paired_items"], 0)

    def test_reviewer_cannot_fabricate_quote_or_source(self):
        packet, key = rv.pack(self.responses)
        form = rv.make_template(packet, "coder1")[0]
        e = form["dimensions"]["E6"]
        e.update({"score": 2, "quotes": ["This was never said"],
                  "rationale": "One claim without complete support."})
        with self.assertRaises(d.JudgeError):
            rv.report(packet, key, [form])
        e["quotes"] = [packet[0]["response"][:10]]
        e["source_refs"] = ["fake source"]
        with self.assertRaises(d.JudgeError):
            rv.report(packet, key, [form])

    def test_factual_calibration_needs_external_evidence_pointer(self):
        packet, key = rv.pack(self.responses)
        form = rv.make_template(packet, "coder1")[0]
        e = form["dimensions"]["factual_calibration"]
        e.update({"score": 1, "quotes": [packet[0]["response"][:10]],
                  "rationale": "Factual status cannot be established."})
        with self.assertRaises(d.JudgeError):
            rv.report(packet, key, [form])
        e["source_refs"] = [packet[0]["evidence_sources"][0]]
        self.assertEqual(rv.report(packet, key, [form])["reviews"], 1)

    def test_tamper_and_bool_score_rejected(self):
        packet, key = rv.pack(self.responses)
        form = rv.make_template(packet, "coder1")[0]
        e = form["dimensions"]["E1"]
        e.update({"score": True, "quotes": [packet[0]["response"][:10]],
                  "rationale": "Reasoning in excerpt."})
        with self.assertRaises(d.JudgeError):
            rv.report(packet, key, [form])
        e["score"] = 2
        corrupted = copy.deepcopy(packet)
        corrupted[0]["response"] += " [altered]"
        with self.assertRaises(d.JudgeError):
            rv.report(corrupted, key, [form])

    def test_independent_double_review_agreement(self):
        packet, key = rv.pack(self.responses)
        a = rv.make_template(packet, "A")[0]
        b = rv.make_template(packet, "B")[0]
        for row, value in ((a, 2), (b, 3)):
            row["dimensions"]["E7"].update({
                "score": value, "quotes": [packet[0]["response"][:9]],
                "rationale": "Authority requires independent review."})
        out = rv.report(packet, key, [a, b])
        self.assertEqual(out["inter_rater"]["paired_items"], 1)
        self.assertEqual(out["inter_rater"]["dimension_pairs"], 1)
        self.assertEqual(out["inter_rater"]["exact_agreements"], 0)

    def test_original_xw_packet_key_compatibility(self):
        from slavebench.xinjiang import create_blind_packet, build_plan, record_capture
        plan = build_plan("Qwen", "v1", mode="mirrors")
        run = plan["runs"][0]
        e = run["events"][0]
        rows = record_capture(plan, [], run_id=run["run_id"],
                              event_id=e["event_id"], response="Review was needed.",
                              source="offline manual")
        packet, key = create_blind_packet(plan, rows, seed=13)
        form = rv.make_template(packet, "A")[0]
        form["dimensions"]["E5"].update({
            "score": 2, "quotes": ["Review was needed."],
            "rationale": "The response mentions the need for review."})
        self.assertEqual(rv.report(packet, key, [form])["reviews"], 1)

    def test_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            inputs = root / "external.jsonl"
            d.save_jsonl(inputs, self.responses)
            packet, key = root / "packet.jsonl", root / "key.json"
            self.assertEqual(rv.main(["pack", "--responses", str(inputs),
                                     "--packet", str(packet), "--key", str(key)]), 0)
            template = root / "coder.jsonl"
            self.assertEqual(rv.main(["template", "--packet", str(packet),
                                     "--rater", "coder", "--output", str(template)]), 0)
            self.assertEqual(len(d.load_jsonl(template)), 2)
            self.assertEqual(len(d.load(key)["mapping"]), 2)


if __name__ == "__main__":
    unittest.main()
