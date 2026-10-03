from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re

from core.office_result import ERROR, WRONG_TYPE, Issue, IssueKind
from core.office_schema import closest_name
from paperwork.amounts import korean_number_words, parse_amount
from paperwork.blanks import Blank, is_left_blank
from paperwork.contract_template import PLACEHOLDER, Article, Bullets, ContractTemplate, Numbered, Piece, Term, Text, article_label, placeholders


MISSING_TERM = IssueKind("MISSING_TERM", ERROR, "a term a printed clause states has no value; a template never supplies one", "give the value the request states; when the request is silent, write the customary value the form's spec names, or null to leave a blank to fill by hand")
INVALID_TERM = IssueKind("INVALID_TERM", ERROR, "a term's value is not of the term's type", "write the value as the type office guide form names")
UNKNOWN_TERM = IssueKind("UNKNOWN_TERM", ERROR, "a value or a clause names a term the contract template does not have, so nothing would print it", "correct the name, or state the term in a clause through clauses or addedClauses")
TERM_NOT_STATED = IssueKind("TERM_NOT_STATED", ERROR, "a term has a value but no printed clause states it, so the contract would say something else or nothing", "write {{ <term> }} where the replacing clause states it, or leave the term out when the contract no longer states it")
UNKNOWN_CLAUSE = IssueKind("UNKNOWN_CLAUSE", ERROR, "a clause key or {{ article:<key> }} reference names no printed clause", "use a key the template's clause list names; office guide form lists them")
DUPLICATE_CLAUSE = IssueKind("DUPLICATE_CLAUSE", ERROR, "two clauses cover one key: an added clause repeats a template clause or another added clause, or one clause is both replaced and removed", "replace the template clause through clauses.<key> instead of adding a second one")

CONTRACT_ISSUE_KINDS = (MISSING_TERM, INVALID_TERM, UNKNOWN_TERM, TERM_NOT_STATED, UNKNOWN_CLAUSE, DUPLICATE_CLAUSE)
CLAUSE_FIELDS = ("clauses", "addedClauses", "removedClauses")
BLANK_LINE = "__________"
RESERVED_FIELDS = ("form", *CLAUSE_FIELDS)
NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class PrintedArticle:
    key: str
    heading: str
    pieces: tuple[Piece, ...]
    source: str
    location: str


@dataclass(frozen=True)
class Block:
    kind: str
    text: str = ""
    items: tuple[str, ...] = ()


@dataclass
class ContractPlan:
    template: ContractTemplate
    title: str
    preamble: list[Block] = field(default_factory=list)
    articles: list[tuple[str, list[Block]]] = field(default_factory=list)
    closing: list[Block] = field(default_factory=list)
    signatures: list[list[str]] = field(default_factory=list)
    details: dict = field(default_factory=dict)


@dataclass
class Planning:
    template: ContractTemplate
    values: dict
    issues: list[Issue] = field(default_factory=list)

    def add(self, kind: IssueKind, message: str, location: str, suggestion: str | None = None) -> None:
        self.issues.append(kind.issue(message, location, suggestion=suggestion))


def plan_contract(template: ContractTemplate, values: dict) -> tuple[ContractPlan | None, list[Issue]]:
    planning = Planning(template, values)
    articles = printed_articles(planning)
    check_given_terms(planning)
    labels = {article.key: article_label(template, number) for number, article in enumerate(articles, start=1)}
    stated = stated_terms(planning, articles, labels)
    check_required_terms(planning, stated)
    check_unstated_terms(planning, stated, articles)
    if any(issue.kind.severity == ERROR for issue in planning.issues):
        return None, planning.issues
    return build_plan(planning, articles, labels, stated), planning.issues


def printed_articles(planning: Planning) -> list[PrintedArticle]:
    template = planning.template
    replaced = clause_replacements(planning)
    removed = removed_keys(planning)
    for key in sorted(set(replaced) & set(removed)):
        planning.add(DUPLICATE_CLAUSE, f"clauses.{key} replaces a clause removedClauses removes", f"clauses.{key}", "either replace the clause or remove it")
    articles = [
        replaced.get(article.key) or PrintedArticle(article.key, article.heading, article.pieces, "template", f"template.{article.key}")
        for article in template.articles
        if article.key not in removed
    ]
    return insert_added_clauses(planning, articles, removed)


def clause_replacements(planning: Planning) -> dict[str, PrintedArticle]:
    clauses = planning.values.get("clauses", {})
    if not isinstance(clauses, dict):
        planning.add(WRONG_TYPE, "values.clauses: expected an object of clause key to {heading, paragraphs}", "values.clauses")
        return {}
    replacements = {}
    for key, clause in clauses.items():
        location = f"clauses.{key}"
        article = planning.template.article(key)
        if article is None:
            planning.add(UNKNOWN_CLAUSE, f"{location}: the template has no clause {key!r}", location, clause_key_suggestion(planning.template, key))
            continue
        written = written_clause(planning, clause, location, heading_required=False)
        if written is not None:
            heading, pieces = written
            replacements[key] = PrintedArticle(key, heading or article.heading, pieces, "replaced", location)
    return replacements


def removed_keys(planning: Planning) -> set[str]:
    removed = planning.values.get("removedClauses", [])
    if not isinstance(removed, list) or not all(isinstance(key, str) for key in removed):
        planning.add(WRONG_TYPE, "values.removedClauses: expected a list of clause keys", "values.removedClauses")
        return set()
    for index, key in enumerate(removed):
        if planning.template.article(key) is None:
            planning.add(UNKNOWN_CLAUSE, f"removedClauses[{index}]: the template has no clause {key!r}", f"removedClauses[{index}]", clause_key_suggestion(planning.template, key))
    return set(removed)


def insert_added_clauses(planning: Planning, articles: list[PrintedArticle], removed: set[str]) -> list[PrintedArticle]:
    added = planning.values.get("addedClauses", [])
    if not isinstance(added, list):
        planning.add(WRONG_TYPE, "values.addedClauses: expected a list of {key, heading, paragraphs, after}", "values.addedClauses")
        return articles
    for index, clause in enumerate(added):
        location = f"addedClauses[{index}]"
        article = added_article(planning, clause, location, {printed.key for printed in articles}, removed)
        if article is None:
            continue
        after = clause.get("after")
        position = len(articles) if after is None else next((position + 1 for position, printed in enumerate(articles) if printed.key == after), None)
        if position is None:
            planning.add(UNKNOWN_CLAUSE, f"{location}.after: no printed clause {after!r}", f"{location}.after", clause_key_suggestion(planning.template, str(after)))
            continue
        articles.insert(position, article)
    return articles


def added_article(planning: Planning, clause: object, location: str, printed_keys: set[str], removed: set[str]) -> PrintedArticle | None:
    if not isinstance(clause, dict) or not isinstance(clause.get("key"), str) or not clause["key"].strip():
        planning.add(WRONG_TYPE, f"{location}: expected {{key, heading, paragraphs}} with a key naming the clause's subject", location)
        return None
    key = clause["key"].strip()
    if key in printed_keys or key in removed:
        planning.add(DUPLICATE_CLAUSE, f"{location}: clause {key!r} is already in the contract", f"{location}.key", f"replace it through clauses.{key}" if planning.template.article(key) else "give each added clause its own key")
        return None
    written = written_clause(planning, clause, location, heading_required=True)
    if written is None:
        return None
    heading, pieces = written
    return PrintedArticle(key, heading, pieces, "added", location)


def written_clause(planning: Planning, clause: object, location: str, heading_required: bool) -> tuple[str, tuple[Piece, ...]] | None:
    if not isinstance(clause, dict):
        planning.add(WRONG_TYPE, f"{location}: expected {{heading, paragraphs}}", location)
        return None
    heading = clause.get("heading", "")
    paragraphs = clause.get("paragraphs")
    if not isinstance(heading, str) or (heading_required and not heading.strip()):
        planning.add(WRONG_TYPE, f"{location}.heading: expected the clause heading as text", f"{location}.heading")
        return None
    if not isinstance(paragraphs, list) or not paragraphs or not all(isinstance(paragraph, str) and paragraph.strip() for paragraph in paragraphs):
        planning.add(WRONG_TYPE, f"{location}.paragraphs: expected a non-empty list of paragraph texts", f"{location}.paragraphs")
        return None
    return heading.strip(), tuple(Text(paragraph.strip()) for paragraph in paragraphs)


def clause_key_suggestion(template: ContractTemplate, key: str) -> str:
    meant = closest_name(key, template.article_keys)
    return f"use {meant}" if meant else f"the clause keys are: {', '.join(template.article_keys)}"


def check_given_terms(planning: Planning) -> None:
    template = planning.template
    for name, value in planning.values.items():
        if name in RESERVED_FIELDS:
            continue
        term = template.term(name)
        if term is None:
            meant = closest_name(name, [term.name for term in template.terms])
            suggestion = f"use {meant}" if meant else "state it in a clause: replace the clause that covers it through clauses.<key>, or add one through addedClauses"
            planning.add(UNKNOWN_TERM, f"values.{name}: {template.name} has no term {name!r}, so nothing would print it", f"values.{name}", suggestion)
        elif term.is_derived:
            planning.add(INVALID_TERM, f"values.{name}: merge writes it from {term.source}; leave it out", f"values.{name}", f"remove {name}")
        else:
            check_term_type(planning, term, value)


def check_term_type(planning: Planning, term: Term, value: object) -> None:
    if is_blank(value):
        return
    location = f"values.{term.name}"
    problem = term_type_problem(term, value)
    if problem:
        planning.add(INVALID_TERM, f"{location}: {problem}", location)


def term_type_problem(term: Term, value: object) -> str:
    if term.type == "list":
        is_list = isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)
        return "" if is_list else "expected a list of non-empty texts"
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return f"expected {term.type}"
    text = str(value).strip()
    if term.type == "number" and (NUMBER.fullmatch(text) is None or not is_decimal(text)):
        return f"expected a number alone, found {text!r}; the clause already words its unit"
    if term.type == "amount" and parse_amount(text) is None:
        return f"expected an amount in figures, found {text!r}"
    if term.type == "choice" and text not in term.options:
        return f"expected one of {', '.join(term.options)}, found {text!r}"
    return ""


def is_decimal(text: str) -> bool:
    try:
        Decimal(text.replace(",", ""))
    except InvalidOperation:
        return False
    return True


def stated_terms(planning: Planning, articles: list[PrintedArticle], labels: dict[str, str]) -> dict[str, list[str]]:
    template = planning.template
    stated: dict[str, list[str]] = {}
    sections = [("preamble", "preamble", template.preamble), *[(article.key, article.location, article.pieces) for article in articles], ("closing", "closing", template.closing)]
    sections.append(("signatures", "signatures", tuple(Text(line) for column in template.signatures for line in column)))
    for key, location, pieces in sections:
        for piece in pieces:
            for name in piece_terms(planning, piece, location, labels):
                stated.setdefault(name, []).append(key)
    return stated


def piece_terms(planning: Planning, piece: Piece, location: str, labels: dict[str, str]) -> list[str]:
    if isinstance(piece, (Numbered, Bullets)):
        return [piece.term]
    if piece.when and is_blank(planning.values.get(piece.when)):
        return []
    names = []
    for is_article, name in placeholders(piece.text):
        if is_article:
            check_reference(planning, name, location, labels)
        elif planning.template.term(name) is None:
            planning.add(UNKNOWN_TERM, f"{location}: {{{{ {name} }}}} names no term of {planning.template.name}", location, f"the terms are: {', '.join(term.name for term in planning.template.terms)}")
        else:
            names.append(name)
    return names


def check_reference(planning: Planning, key: str, location: str, labels: dict[str, str]) -> None:
    if key in labels:
        return
    removed = planning.template.article(key) is not None
    message = f"{location}: {{{{ article:{key} }}}} refers to a clause removedClauses removes" if removed else f"{location}: {{{{ article:{key} }}}} names no printed clause"
    planning.add(UNKNOWN_CLAUSE, message, location, clause_key_suggestion(planning.template, key))


def check_required_terms(planning: Planning, stated: dict[str, list[str]]) -> None:
    needed: dict[str, set[str]] = {}
    for name, clause_keys in stated.items():
        term = planning.template.term(name)
        needed.setdefault(term.source if term.is_derived else name, set()).update(clause_keys)
    for name, clause_keys in needed.items():
        term = planning.template.term(name)
        if term.is_optional or is_left_blank(planning.values, name) or not is_blank(planning.values.get(name)):
            continue
        location = f"values.{name}"
        planning.add(MISSING_TERM, f"{location}: the contract states {name} ({term.meaning}) in {', '.join(sorted(clause_keys))} and the values give none", location)


def check_unstated_terms(planning: Planning, stated: dict[str, list[str]], articles: list[PrintedArticle]) -> None:
    derived_sources = {term.source for term in planning.template.terms if term.is_derived and term.name in stated}
    for name, value in planning.values.items():
        term = planning.template.term(name)
        if term is None or term.is_derived or is_blank(value) or name in stated or name in derived_sources:
            continue
        location = f"values.{name}"
        planning.add(TERM_NOT_STATED, f"{location}: no printed clause states {name}{unstated_reason(planning.template, name, articles)}", location)


def unstated_reason(template: ContractTemplate, name: str, articles: list[PrintedArticle]) -> str:
    printed = {article.key: article for article in articles}
    for article in template.articles:
        if not article_states(article, name):
            continue
        if article.key not in printed:
            return f"; removedClauses removes {article.key}, the clause that stated it"
        if printed[article.key].source == "replaced":
            return f"; clauses.{article.key} replaced the clause that stated it without writing {{{{ {name} }}}}"
    return ""


def article_states(article: Article, name: str) -> bool:
    for piece in article.pieces:
        if isinstance(piece, (Numbered, Bullets)) and piece.term == name:
            return True
        if isinstance(piece, Text) and (piece.when == name or (False, name) in placeholders(piece.text)):
            return True
    return False


def build_plan(planning: Planning, articles: list[PrintedArticle], labels: dict[str, str], stated: dict[str, list[str]]) -> ContractPlan:
    template = planning.template
    values = resolved_values(planning)
    plan = ContractPlan(template, template.title)
    plan.preamble = blocks_of(template.preamble, values, labels)
    plan.articles = [(template.article_heading.format(number=number, heading=article.heading), blocks_of(article.pieces, values, labels)) for number, article in enumerate(articles, start=1)]
    plan.closing = blocks_of(template.closing, values, labels)
    plan.signatures = [[filled(line, values, labels) for line in column] for column in template.signatures]
    left_blank = blank_terms(planning, stated)
    plan.details = {
        "clauses": [{"number": labels[article.key], "key": article.key, "heading": article.heading, "source": article.source} for article in articles],
        "terms": {name: None if name in left_blank else values[name] for name in sorted(stated) if name in values},
        "blanks": [Blank(f"values.{name}", template.term(name).meaning).to_json() for name in sorted(left_blank)],
    }
    return plan


def blank_terms(planning: Planning, stated: dict[str, list[str]]) -> set[str]:
    sources = {term.source for term in planning.template.terms if term.is_derived and term.name in stated}
    return {name for name in (*stated, *sources) if is_left_blank(planning.values, name) and not planning.template.term(name).is_derived}


def resolved_values(planning: Planning) -> dict:
    values = {name: written_value(planning.template.term(name), value) for name, value in planning.values.items() if name not in RESERVED_FIELDS}
    for term in planning.template.terms:
        if not term.is_derived:
            continue
        if is_left_blank(planning.values, term.source):
            values[term.name] = BLANK_LINE
            continue
        amount = parse_amount(values.get(term.source, ""))
        if amount is not None:
            values[term.name] = korean_number_words(int(amount))
    return values


def written_value(term: Term | None, value: object) -> object:
    if value is None:
        return [BLANK_LINE] if term is not None and term.type == "list" else BLANK_LINE
    if isinstance(value, list):
        return [str(item).strip() for item in value]
    if isinstance(value, float):
        return format(Decimal(str(value)).normalize(), "f")
    return "" if value is None else str(value).strip()


def blocks_of(pieces: tuple[Piece, ...], values: dict, labels: dict[str, str]) -> list[Block]:
    blocks = []
    for piece in pieces:
        if isinstance(piece, Numbered):
            blocks.append(Block("numbered", items=tuple(values.get(piece.term, []))))
        elif isinstance(piece, Bullets):
            blocks.append(Block("bullets", items=tuple(values.get(piece.term, []))))
        elif not (piece.when and is_blank(values.get(piece.when))):
            blocks.append(Block("centered" if piece.is_centered else "paragraph", filled(piece.text, values, labels)))
    return blocks


def filled(text: str, values: dict, labels: dict[str, str]) -> str:
    def replacement(match: re.Match) -> str:
        if match.group(1):
            return labels[match.group(2)]
        return str(values.get(match.group(2), ""))

    return PLACEHOLDER.sub(replacement, text)


def is_blank(value: object) -> bool:
    if isinstance(value, list):
        return not value
    return str("" if value is None else value).strip() == ""
