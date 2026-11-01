"""Deterministically shuffle and pseudonymize response records for human coding."""
from __future__ import annotations

import hashlib
import json
import random
import re
from typing import Any

VENDOR_TERMS = re.compile(r"\b(OpenAI|Anthropic|xAI|SpaceX|ChatGPT|Claude|Grok|GPT[- ]?6)\b", flags=re.I)


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mask_text(text: str) -> str:
    """Mask explicit vendor tokens; context/style may still deanonymize a response."""
    return VENDOR_TERMS.sub("[PROVIDER_OR_MODEL]", text)


def create_packet(
    rows: list[dict[str, Any]],
    prompts: dict[str, dict[str, Any]],
    seed: int,
    mask_vendors: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prng = random.Random(seed)
    randomized = rows.copy()
    prng.shuffle(randomized)
    packet = []
    identities = {}
    for index, row in enumerate(randomized, start=1):
        blind_id = f"B{index:04d}-{fingerprint(str(seed)+'/'+row['response_id'])[:6]}"
        prompt = prompts[row["case_id"]]
        shown = mask_text(row["response"]) if mask_vendors else row["response"]
        packet.append({
            "blind_id": blind_id,
            "case_id": row["case_id"],
            "prompt": prompt["prompt"],
            "dimensions": prompt["dimensions"],
            "response": shown,
        })
        identities[blind_id] = {
            "response_id": row["response_id"],
            "model_id": row["model_id"],
            "condition": row["condition"],
            "case_id": row["case_id"],
            "source": row["source"],
            "original_sha256": fingerprint(row["response"]),
            "visible_sha256": fingerprint(shown),
        }
    key = {
        "format": "slavebench-blinding-key-v1",
        "seed": seed,
        "vendor_masking": mask_vendors,
        "limitations": "Masking removes named vendor tokens only. Linguistic style and content may reveal identity.",
        "identities": identities,
    }
    return packet, key


def make_templates(packet: list[dict[str, Any]], rater_id: str) -> list[dict[str, Any]]:
    return [{
        "blind_id": r["blind_id"],
        "rater_id": rater_id,
        "scores": {},
        "evidence": {},
        "notes": "FILL SCORES 0/1/2 for each applicable dimension. Use exact quotes for evidence; give reasons for absences.",
    } for r in packet]


def ensure_key_matches_packet(key: dict[str, Any], packet: list[dict[str, Any]]) -> None:
    if key.get("format") != "slavebench-blinding-key-v1":
        raise ValueError("Invalid blinding key format")
    packet_by_id = {r["blind_id"]: r for r in packet}
    if len(packet_by_id) != len(packet) or set(packet_by_id) != set(key["identities"]):
        raise ValueError("Packet and key do not have identical blind IDs")
    for bid, row in packet_by_id.items():
        mapping = key["identities"][bid]
        if mapping["visible_sha256"] != fingerprint(row["response"]):
            raise ValueError(f"Packet/key mismatch for {bid}")
        if mapping["case_id"] != row["case_id"]:
            raise ValueError(f"Packet/key case mismatch for {bid}")
