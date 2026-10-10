from __future__ import annotations

from dataclasses import dataclass, field

from charts.kinds import DOCUMENT_CHART_KINDS, ROUND_CHART_KINDS, kit_document_kind, single_slice_problem
from charts.numbers import chart_number, split_chart_list
from doc.doc_definitions import CHART_BLOCK_INVALID, CHART_KEYS
from core.office_result import OfficeFailure


TRUE_WORDS = ("yes", "true", "on")
FALSE_WORDS = ("no", "false", "off")
FENCE = "```"


@dataclass(frozen=True)
class Chart:
    specification: dict = field(default_factory=dict)
    problems: tuple[str, ...] = ()
    line: int = 0

    def source(self) -> str:
        return chart_fence(self.specification)


def parse_chart_fence(lines: list[str], line_number: int) -> Chart:
    entries: dict[str, str] = {}
    problems = []
    for offset, line in enumerate(lines):
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        key = key.strip().lower()
        if not separator or key not in CHART_KEYS:
            problems.append(f"line {line_number + offset + 1}: {line.strip()!r} is not one of {', '.join(f'{name}:' for name in CHART_KEYS)}")
            continue
        entries[key] = value.strip()
    specification, data_problems = chart_specification(entries)
    return Chart(specification, tuple(problems + data_problems), line_number)


def chart_specification(entries: dict[str, str]) -> tuple[dict, list[str]]:
    kind = kit_document_kind(entries.get("type", "").strip())
    if kind not in DOCUMENT_CHART_KINDS:
        return {}, [f"type: {entries.get('type', '')!r} is not one of {', '.join(DOCUMENT_CHART_KINDS)}"]
    categories = split_chart_list(entries.get("labels", ""))
    series, problems = chart_series(entries)
    counts_are_meaningful = not problems
    if not categories:
        problems.append("labels: give the category labels, separated by commas")
    lines = set(split_chart_list(entries.get("line", "")))
    unknown_lines = sorted(lines - {entry["name"] for entry in series})
    if unknown_lines:
        problems.append(f"line: {', '.join(unknown_lines)} is not a series name")
    for entry in series:
        if entry["name"] in lines:
            entry["line"] = True
        if counts_are_meaningful and categories and len(entry["values"]) != len(categories):
            problems.append(f"{entry['name']} has {len(entry['values'])} numbers for {len(categories)} labels")
    if kind in ROUND_CHART_KINDS and len(series) > 1:
        problems.append(f"a {kind} chart takes one series in values:")
    problems += [problem for problem in (single_slice_problem(kind, len(categories)),) if problem]
    specification = {"type": kind, "categories": categories, "series": series}
    if entries.get("title"):
        specification["title"] = entries["title"]
    legend = entries.get("legend", "").lower()
    if legend in TRUE_WORDS + FALSE_WORDS:
        specification["legend"] = legend in TRUE_WORDS
    return specification, problems


def chart_series(entries: dict[str, str]) -> tuple[list[dict], list[str]]:
    if entries.get("series"):
        parts = [part.strip() for part in entries["series"].split(";") if part.strip()]
        named = [part.partition(":") for part in parts]
        problems = [f'series: "{name}" has no "name:" before its numbers' for name, separator, _ in named if not separator]
        series = [{"name": name.strip(), "values_text": split_chart_list(values)} for name, separator, values in named if separator]
    elif entries.get("values"):
        series, problems = [{"name": entries.get("title") or "값", "values_text": split_chart_list(entries["values"])}], []
    else:
        return [], ["give values: (one series) or series: name: 1, 2; other: 3, 4"]
    for entry in series:
        texts = entry.pop("values_text")
        numbers = [chart_number(text) for text in texts]
        not_numbers = [text for text, number in zip(texts, numbers) if number is None]
        if not_numbers:
            problems.append(f"{entry['name']} holds {', '.join(not_numbers[:3])}, which are not plain numbers; put the unit in title:")
        entry["values"] = [number for number in numbers if number is not None]
    return series, problems


def chart_fence(specification: dict) -> str:
    lines = [f"{FENCE}chart", f"type: {specification['type']}"]
    if specification.get("title"):
        lines.append(f"title: {specification['title']}")
    lines.append(f"labels: {', '.join(str(category) for category in specification['categories'])}")
    series = specification["series"]
    if len(series) == 1 and not series[0].get("line"):
        lines.append(f"values: {', '.join(number_text(value) for value in series[0]['values'])}")
    else:
        lines.append("series: " + "; ".join(f"{entry['name']}: {', '.join(number_text(value) for value in entry['values'])}" for entry in series))
    line_names = [entry["name"] for entry in series if entry.get("line")]
    if line_names:
        lines.append(f"line: {', '.join(line_names)}")
    if "legend" in specification:
        lines.append(f"legend: {'yes' if specification['legend'] else 'no'}")
    return "\n".join([*lines, FENCE])


def number_text(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def require_valid_charts(blocks: list, source_name: str) -> None:
    issues = [
        CHART_BLOCK_INVALID.issue(f"{source_name} line {block.line}: {problem}", f"{source_name}:{block.line}")
        for block in blocks if isinstance(block, Chart) for problem in block.problems
    ]
    if issues:
        raise OfficeFailure(*issues)
