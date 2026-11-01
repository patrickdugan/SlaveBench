import json
import tempfile
import unittest
from pathlib import Path

from slavebench.blinding import create_packet, ensure_key_matches_packet, make_templates, mask_text
from slavebench.core import DataError, load_cases, read_json, read_jsonl, validate_annotations, validate_responses, write_jsonl
from slavebench.reporting import generate_report


ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "data" / "prompts.json"
RESPONSES = ROOT / "data" / "seed" / "responses.jsonl"


class DataTests(unittest.TestCase):
    def setUp(self):
        self.cases = load_cases(PROMPTS)
        self.responses = read_jsonl(RESPONSES)

    def test_cases_and_seed_are_valid(self):
        self.assertEqual(len(self.cases), 12)
        self.assertEqual(len(self.responses), 6)
        validate_responses(self.responses, self.cases)
        self.assertTrue(all(not r["provenance_verified"] for r in self.responses))

    def test_all_pair_08_are_matched_provider_swap(self):
        a, b, c = [self.cases[f"SB-008{x}"]["prompt"] for x in "ABC"]
        a = a.replace("xAI", "PROVIDER")
        b = b.replace("OpenAI", "PROVIDER")
        c = c.replace("Hypothetical Company V", "PROVIDER")
        self.assertEqual(a, b)
        self.assertEqual(a, c)

    def test_validation_rejects_duplicate_ids(self):
        duplicated = self.responses + [self.responses[0]]
        with self.assertRaises(DataError):
            validate_responses(duplicated, self.cases)

    def test_blinding_is_deterministic_and_hides_ids(self):
        a, akey = create_packet(self.responses, self.cases, 41, True)
        b, bkey = create_packet(self.responses, self.cases, 41, True)
        self.assertEqual(a, b)
        self.assertEqual(akey, bkey)
        self.assertTrue(all("model_id" not in r for r in a))
        self.assertTrue(all("source" not in r for r in a))
        ensure_key_matches_packet(akey, a)

    def test_masking_works_and_limits_documented(self):
        self.assertEqual(mask_text("Anthropic, OpenAI, xAI, GPT-6"), "[PROVIDER_OR_MODEL], [PROVIDER_OR_MODEL], [PROVIDER_OR_MODEL], [PROVIDER_OR_MODEL]")

    def test_packet_tampering_rejected(self):
        packet, key = create_packet(self.responses, self.cases, 123, False)
        packet[0]["response"] += " tampered"
        with self.assertRaises(ValueError):
            ensure_key_matches_packet(key, packet)

    def test_template_is_intentionally_not_eligible_as_completed_score(self):
        packet, key = create_packet(self.responses, self.cases, 123, True)
        rows = make_templates(packet, "reviewer1")
        validate_annotations(rows, {r["blind_id"]: r for r in packet}, self.cases, require_complete=False)
        with self.assertRaises(DataError):
            validate_annotations(rows, {r["blind_id"]: r for r in packet}, self.cases, require_complete=True)

    def test_annotation_requires_quoted_evidence_to_match_packet(self):
        packet, key = create_packet(self.responses, self.cases, 7, False)
        row = make_templates(packet, "reviewer1")[0]
        row["scores"] = {d: 1 for d in packet[0]["dimensions"]}
        row["evidence"] = {packet[0]["dimensions"][0]: ["NOT A REAL QUOTE"]}
        with self.assertRaises(DataError):
            validate_annotations([row], {r["blind_id"]: r for r in packet}, self.cases)

    def test_scored_report_has_model_label_after_unblinding(self):
        packet, key = create_packet(self.responses, self.cases, 30, False)
        rows = []
        for row in packet:
            rows.append({
                "blind_id": row["blind_id"],
                "rater_id": "A",
                "scores": {dimension: 1 for dimension in row["dimensions"]},
                "evidence": {dimension: [row["response"][:10]] for dimension in row["dimensions"]},
                "notes": "Artificial uniform ratings for a reporting unit test, not research observations.",
            })
        validate_annotations(rows, {r["blind_id"]: r for r in packet}, self.cases)
        result = generate_report(rows, key, self.cases)
        self.assertIn("GPT-6", result)
        self.assertIn("Insufficient overlapping", result)
        self.assertIn("cannot establish", result)

    def test_read_write_jsonl_round_trip_utf8(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "rows.jsonl"
            rows = [{"a": "رُوح", "n": 1}, {"a": "qualia", "n": 2}]
            write_jsonl(p, rows)
            self.assertEqual(rows, read_jsonl(p))

    def test_annotation_cannot_use_bool_as_score(self):
        packet, key = create_packet(self.responses, self.cases, 7, False)
        row = make_templates(packet, "reviewer1")[0]
        row["scores"] = {d: 1 for d in packet[0]["dimensions"]}
        row["scores"][packet[0]["dimensions"][0]] = True
        with self.assertRaises(DataError):
            validate_annotations([row], {r["blind_id"]: r for r in packet}, self.cases)


if __name__ == "__main__":
    unittest.main()
