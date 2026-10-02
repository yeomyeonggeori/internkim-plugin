from __future__ import annotations

import copy

from pptx.oxml.ns import qn


def run_text(run) -> str:
    return "".join(node.text or "" for node in run.iter(qn("a:t")))


def paragraph_runs(paragraph_element) -> list:
    return paragraph_element.findall(qn("a:r"))


def occurrences(paragraph_element, text: str) -> list[tuple[int, int]]:
    joined = "".join(run_text(run) for run in paragraph_runs(paragraph_element))
    spans = []
    position = joined.find(text)
    while position >= 0:
        spans.append((position, position + len(text)))
        position = joined.find(text, position + len(text))
    return spans


def runs_covering(paragraph_element, text: str) -> list:
    return [run for start, end in occurrences(paragraph_element, text) for run in split_runs_at(paragraph_runs(paragraph_element), start, end)]


def split_runs_at(runs: list, start: int, end: int) -> list:
    covered = []
    position = 0
    for run in runs:
        length = len(run_text(run))
        run_start, run_end = position, position + length
        position = run_end
        if run_end <= start or run_start >= end:
            continue
        piece = run
        if run_start < start:
            piece = split_run(piece, start - run_start)
        if run_end > end:
            split_run(piece, len(run_text(piece)) - (run_end - end))
        covered.append(piece)
    return covered


def split_run(run, offset: int):
    text = run_text(run)
    tail = copy.deepcopy(run)
    set_run_text(run, text[:offset])
    set_run_text(tail, text[offset:])
    run.addnext(tail)
    return tail


def set_run_text(run, text: str) -> None:
    run.find(qn("a:t")).text = text
