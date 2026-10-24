from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from doc.blocks.charts import FENCE
from paperwork.stationery import Letterhead, Signer

LETTERHEAD_FENCE = "letterhead"
SIGNATURE_FENCE = "signature"
STATIONERY_FENCES = (LETTERHEAD_FENCE, SIGNATURE_FENCE)
ALIGNMENTS = ("center", "left")


@dataclass(frozen=True)
class LetterheadBlock:
    letterhead: Letterhead

    @property
    def text(self) -> str:
        return "\n".join(line for line in (self.letterhead.name, *self.letterhead.details) if line)

    def source(self) -> str:
        return stationery_fence(LETTERHEAD_FENCE, asdict(self.letterhead))


@dataclass(frozen=True)
class SignatureBlock:
    signer: Signer
    alignment: str = "center"

    @property
    def text(self) -> str:
        return "\n".join(self.signer.lines)

    def source(self) -> str:
        return stationery_fence(SIGNATURE_FENCE, {**asdict(self.signer), "alignment": self.alignment})


def stationery_fence(kind: str, data: dict) -> str:
    return "\n".join((f"{FENCE}{kind}", json.dumps(data, ensure_ascii=False), FENCE))


def stationery_fence_kind(stripped_line: str) -> str | None:
    kind = stripped_line[len(FENCE):].strip().lower() if stripped_line.startswith(FENCE) else ""
    return kind if kind in STATIONERY_FENCES else None


def stationery_block(lines: list[str], index: int):
    kind = stationery_fence_kind(lines[index].strip())
    end = next((position for position in range(index + 1, len(lines)) if lines[position].strip() == FENCE), len(lines))
    data = json.loads("".join(lines[index + 1:end]) or "{}")
    return parsed_block(kind, data), end + 1


def parsed_block(kind: str | None, data: dict):
    if kind == LETTERHEAD_FENCE:
        return LetterheadBlock(Letterhead(str(data.get("name") or ""), tuple(str(line) for line in data.get("details") or ()), str(data.get("logo_path") or "")))
    alignment = data.get("alignment") if data.get("alignment") in ALIGNMENTS else "center"
    return SignatureBlock(Signer(tuple(str(line) for line in data.get("lines") or ()), str(data.get("seal_mark") or ""), str(data.get("stamp_path") or "")), alignment)
