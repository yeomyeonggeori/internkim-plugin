from __future__ import annotations

from core.office_commands import EVERY_KIND, FLAGS_BY_NAME, POSITIONALS, Flag, Route, Verb, find_route, find_verb, route_label
from core.office_inputs import KINDS_BY_NAME, office_file
from core.office_outputs import output_file
from core.office_result import OfficeArgumentParser


def route_parser(verb_name: str, kind_name: str = EVERY_KIND, **defaults: object) -> OfficeArgumentParser:
    verb = find_verb(verb_name)
    route = find_route(verb_name, kind_name)
    parser = OfficeArgumentParser(prog=f"office {verb.name}", description=route_description(verb, route))
    for positional in verb.positionals:
        parser.add_argument(positional, type=positional_type(verb, route, positional), help=POSITIONALS[positional])
    for name in route.flags:
        add_flag(parser, FLAGS_BY_NAME[name], defaults.get(FLAGS_BY_NAME[name].destination))
    return parser


def route_arguments(verb_name: str, kind_name: str = EVERY_KIND, **defaults: object):
    return route_parser(verb_name, kind_name, **defaults).parse_args()


def route_description(verb: Verb, route: Route) -> str:
    sentence = verb.summary[0].upper() + verb.summary[1:]
    if not route.summary:
        return f"{sentence}."
    outputs = f" to {' '.join(route.outputs)}" if route.outputs else ""
    return f"{sentence}. {route_label(route)}{outputs}: {route.summary}."


def positional_type(verb: Verb, route: Route, positional: str):
    if positional == verb.subject and route.reads_its_kind and route.kind in KINDS_BY_NAME:
        return office_file(route.kind)
    if positional == "output" and route.outputs:
        return output_file(*route.outputs)
    return None


def add_flag(parser: OfficeArgumentParser, flag: Flag, default: object) -> None:
    chosen_default = flag.default if default is None else default
    meaning = f"{flag.meaning}; default {chosen_default}" if default is not None else flag.meaning
    if not flag.takes_value:
        parser.add_argument(flag.name, action="store_true", help=meaning)
        return
    options = {"metavar": flag.value, "help": meaning, "type": flag.number}
    if flag.choices:
        options["choices"] = flag.choices
    if flag.repeatable:
        parser.add_argument(flag.name, action="append", default=[], **options)
        return
    parser.add_argument(flag.name, default=chosen_default, **options)
