from __future__ import annotations

import json

from deck.deck_kit import KIT_PATH


TYPEFACE_PATH = KIT_PATH / "typeface.json"
TYPEFACE = json.loads(TYPEFACE_PATH.read_text(encoding="utf-8"))
TYPE_QUESTION = TYPEFACE["questions"]["type"]
TYPE_OPTIONS = tuple(TYPE_QUESTION["options"])


def decided_type(deck_design: dict | None) -> str:
    decided = ((deck_design or {}).get("choices") or {}).get("type")
    if not isinstance(decided, dict) or decided.get("option") not in TYPE_OPTIONS:
        return TYPE_QUESTION["fallback"]
    probability = (decided.get("probabilities") or {}).get(decided["option"])
    if probability is not None and float(probability) < TYPEFACE["confidence"]:
        return TYPE_QUESTION["fallback"]
    return decided["option"]


def type_pairing(type_option: str) -> dict:
    return TYPEFACE["types"][type_option]
