from __future__ import annotations

from dataclasses import dataclass, field
import re
import zipfile

from office_result import ERROR, WARNING, Issue, IssueKind, OfficeFailure
from office_schema import AnyOf, CellValue, ListOf, MapOf
from run_replacement import replace_span


PLACEHOLDER = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
MISSING = object()

MERGE_VALUES = MapOf(AnyOf((CellValue(), ListOf(CellValue()), MapOf(CellValue(), key="name"), ListOf(MapOf(CellValue(), key="name"))), name="a cell, a list, an object, or a list of objects; {{ a.b }} reads a field and {{ a.0.b }} one item"), key="placeholder name")

UNRESOLVED_PLACEHOLDER = IssueKind("UNRESOLVED_PLACEHOLDER", ERROR, "the template uses a placeholder the values file does not give", "add the value to the values file")
UNUSED_VALUE = IssueKind("UNUSED_VALUE", WARNING, "the values file gives a name the template never uses", "check the name's spelling against the template")
TEMPLATE_SYNTAX_ERROR = IssueKind("TEMPLATE_SYNTAX_ERROR", ERROR, "the template's placeholder syntax does not parse", "fix the {{ }} or {% %} tag the message names")
LIST_NEEDS_A_ROW = IssueKind("LIST_NEEDS_A_ROW", ERROR, "a placeholder names a list outside a repeatable row, so there is no single value to write", "name one item such as {{ items.0.name }}, or put the placeholder in a table row so the row repeats once per item")

PACKAGE_MERGE_ISSUE_KINDS = (UNRESOLVED_PLACEHOLDER, UNUSED_VALUE, LIST_NEEDS_A_ROW)


@dataclass
class MergeReport:
    values: dict
    filled: int = 0
    used_names: set = field(default_factory=set)
    problems: list = field(default_factory=list)
    placeholder_names: set = field(default_factory=set)

    def resolve(self, path: str, location: str, scope: dict | None = None) -> object:
        self.placeholder_names.add(path)
        value = lookup(scope if scope is not None else self.values, path)
        if value is MISSING:
            self.problems.append(UNRESOLVED_PLACEHOLDER.issue(f"{location} uses {{{{ {path} }}}} but the values file has no {path!r}", location))
            return MISSING
        if isinstance(value, (list, dict)):
            self.problems.append(LIST_NEEDS_A_ROW.issue(f"{location}: {{{{ {path} }}}} names a {type(value).__name__}, which has no single text", location))
            return MISSING
        self.used_names.add(path.split(".", 1)[0])
        self.filled += 1
        return value

    def mark_used(self, name: str) -> None:
        self.used_names.add(name)

    def require_complete(self) -> None:
        if self.problems:
            raise OfficeFailure(*self.problems)

    def unused_issues(self) -> tuple[Issue, ...]:
        return tuple(UNUSED_VALUE.issue(f"values.{name} is not used by the template", f"values.{name}") for name in sorted(set(self.values) - self.used_names))


def lookup(values: object, path: str) -> object:
    current = values
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return MISSING
    return current


def text_of(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def placeholder_paths(text: str) -> list[str]:
    return PLACEHOLDER.findall(text)


def fill_text_nodes(nodes: list, report: MergeReport, location: str, scope: dict | None = None) -> bool:
    joined = "".join(node.text or "" for node in nodes)
    matches = list(PLACEHOLDER.finditer(joined))
    if not matches:
        return False
    for node in nodes:
        node.text = node.text or ""
    for match in reversed(matches):
        value = report.resolve(match.group(1), location, scope)
        if value is not MISSING:
            replace_span(nodes, match.start(), match.end(), text_of(value))
    return True


def repeated_list_name(text: str, values: dict) -> str | None:
    for path in placeholder_paths(text):
        name, _, rest = path.partition(".")
        if isinstance(values.get(name), list) and rest and not rest.split(".", 1)[0].isdigit():
            return name
    return None


def index_list_placeholders(nodes: list, list_name: str, index: int) -> None:
    joined = "".join(node.text or "" for node in nodes)
    for node in nodes:
        node.text = node.text or ""
    for match in reversed(list(PLACEHOLDER.finditer(joined))):
        name, _, rest = match.group(1).partition(".")
        if name == list_name and rest and not rest.split(".", 1)[0].isdigit():
            replace_span(nodes, match.start(), match.end(), f"{{{{ {list_name}.{index}.{rest} }}}}")


def list_outside_row_issues(text: str, values: dict, where: str) -> list[Issue]:
    issues = []
    for path in placeholder_paths(text):
        name, _, rest = path.partition(".")
        if isinstance(values.get(name), list) and not (rest and rest.split(".", 1)[0].isdigit()):
            issues.append(LIST_NEEDS_A_ROW.issue(f"{where}: {{{{ {path} }}}} names the list {name!r} outside a table row, so there is no single value to write", f"values.{name}"))
    return issues


def whole_placeholder(text: str) -> str | None:
    match = PLACEHOLDER.fullmatch(text.strip())
    return match.group(1) if match else None


def write_package(template_path: str, parts: dict[str, bytes], output_path: str) -> None:
    with zipfile.ZipFile(template_path) as source, zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            target.writestr(info, parts.get(info.filename, source.read(info.filename)))
