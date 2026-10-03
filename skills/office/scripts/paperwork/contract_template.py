from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


PLACEHOLDER = re.compile(r"\{\{\s*(article:)?([A-Za-z]\w*)\s*\}\}")
TERM_TYPES = {
    "text": "text",
    "number": "a number alone, such as 10 or 1.25; the clause words its unit",
    "amount": "an amount in figures, with or without thousands separators",
    "choice": "one of the listed options",
    "list": "a non-empty list of texts, one item each",
    "amountInWords": "written by merge from another term; never given",
}


@dataclass(frozen=True)
class Term:
    name: str
    type: str
    meaning: str
    is_optional: bool = False
    options: tuple[str, ...] = ()
    source: str = ""

    @property
    def is_derived(self) -> bool:
        return self.type == "amountInWords"

    def describe(self) -> str:
        options = f" ({' | '.join(self.options)})" if self.options else ""
        blank = "; may be blank" if self.is_optional else ""
        return f"{self.name}: {self.type}{options}, {self.meaning}{blank}"


@dataclass(frozen=True)
class Text:
    text: str
    when: str = ""
    is_centered: bool = False


@dataclass(frozen=True)
class Numbered:
    term: str


@dataclass(frozen=True)
class Bullets:
    term: str


Piece = Text | Numbered | Bullets


@dataclass(frozen=True)
class Article:
    key: str
    heading: str
    pieces: tuple[Piece, ...]


@dataclass(frozen=True)
class ContractTemplate:
    name: str
    title: str
    article_heading: str
    terms: tuple[Term, ...]
    preamble: tuple[Piece, ...]
    articles: tuple[Article, ...]
    closing: tuple[Piece, ...]
    signatures: tuple[tuple[str, ...], ...]

    def term(self, name: str) -> Term | None:
        return next((term for term in self.terms if term.name == name), None)

    def article(self, key: str) -> Article | None:
        return next((article for article in self.articles if article.key == key), None)

    @property
    def article_keys(self) -> list[str]:
        return [article.key for article in self.articles]


def load_template(path: Path) -> ContractTemplate:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ContractTemplate(
        name=path.stem,
        title=data["title"],
        article_heading=data["articleHeading"],
        terms=tuple(term_of(entry) for entry in data["terms"]),
        preamble=tuple(piece_of(entry) for entry in data["preamble"]),
        articles=tuple(Article(entry["key"], entry["heading"], tuple(piece_of(piece) for piece in entry["paragraphs"])) for entry in data["articles"]),
        closing=tuple(piece_of(entry) for entry in data["closing"]),
        signatures=tuple(tuple(column) for column in data["signatures"]),
    )


def term_of(entry: dict) -> Term:
    return Term(
        name=entry["name"],
        type=entry["type"],
        meaning=entry["meaning"],
        is_optional=entry.get("optional", False),
        options=tuple(entry.get("options", ())),
        source=entry.get("of", ""),
    )


def piece_of(entry: str | dict) -> Piece:
    if isinstance(entry, str):
        return Text(entry)
    if "numbered" in entry:
        return Numbered(entry["numbered"])
    if "bullets" in entry:
        return Bullets(entry["bullets"])
    if "centered" in entry:
        return Text(entry["centered"], is_centered=True)
    return Text(entry["text"], when=entry.get("when", ""))


def article_label(template: ContractTemplate, number: int) -> str:
    return template.article_heading.split(" ", 1)[0].format(number=number, heading="")


def placeholders(text: str) -> list[tuple[bool, str]]:
    return [(bool(match.group(1)), match.group(2)) for match in PLACEHOLDER.finditer(text)]
