from __future__ import annotations

from core.office_commands import (
    EVERY_KIND,
    FLAGS_BY_NAME,
    TOOLS,
    VERBS,
    Route,
    Verb,
    conversion_sources,
    conversion_targets,
    route_label,
    verb_routes,
)


USAGE_LINE = "usage: office <verb> <file> [options]; the file's format picks what the verb does"
CLOSING_LINE = "office <verb> --help lists a verb's options; office guide <verb> <kind> its fields, operations and issue codes."


def usage_text() -> str:
    lines = [USAGE_LINE, ""]
    for verb in VERBS:
        lines.extend(verb_lines(verb))
    width = max(len(tool.usage) for tool in TOOLS)
    lines.extend(f"{tool.usage.ljust(width)}  {tool.summary}" for tool in TOOLS)
    return "\n".join([*lines, "", CLOSING_LINE])


def verb_lines(verb: Verb) -> list[str]:
    return [f"{verb.usage}  {verb.summary}", *indented(kind_lines(verb))]


def kind_lines(verb: Verb) -> list[str]:
    if verb.name == "convert":
        return conversion_lines()
    pairs = [(route_accepts(route), route.summary) for route in verb_routes(verb.name) if route.kind != EVERY_KIND]
    if not pairs:
        return []
    width = max(len(accepts) for accepts, _ in pairs)
    return [f"{accepts.ljust(width)}  {summary}" for accepts, summary in pairs]


def route_accepts(route: Route) -> str:
    outputs = f" → {' '.join(route.outputs)}" if route.outputs and route.verb == "create" else ""
    return f"{route_label(route)}{outputs}"


def conversion_lines() -> list[str]:
    sources = conversion_sources()
    width = max(len(source) for source in sources) + 1
    return [f"{('.' + source).ljust(width)} → {' '.join('.' + target for target in conversion_targets(source))}" for source in sources]


def indented(lines: list[str]) -> list[str]:
    return [f"    {line}" for line in lines]


def verb_help_text(verb: Verb, with_kinds: bool = True) -> str:
    lines = [f"usage: office {verb.usage} [options]", verb.summary[0].upper() + verb.summary[1:] + "."]
    if with_kinds:
        lines.extend(["", *(indented(kind_lines(verb)) or [f"    {route.summary}" for route in verb_routes(verb.name) if route.summary])])
    options = option_lines(verb)
    if options:
        lines.extend(["", "options (the kinds that take each):", *indented(options)])
    return "\n".join(lines)


def option_lines(verb: Verb) -> list[str]:
    routes = verb_routes(verb.name)
    names = list(dict.fromkeys(name for route in routes for name in route.flags))
    rows = [(flag_usage(name), flag_kinds(name, routes), FLAGS_BY_NAME[name].meaning) for name in names]
    if not rows:
        return []
    width = max(len(usage) for usage, _, _ in rows)
    return [f"{usage.ljust(width)}  {kinds}{meaning}" for usage, kinds, meaning in rows]


def flag_usage(name: str) -> str:
    flag = FLAGS_BY_NAME[name]
    return f"{name} {flag.value}" if flag.takes_value else name


def flag_kinds(name: str, routes: list[Route]) -> str:
    taking = [route for route in routes if name in route.flags]
    if len(taking) == len(routes) or any(route.kind == EVERY_KIND for route in taking):
        return ""
    return " ".join(dict.fromkeys(route_label(route) for route in taking)) + ": "

