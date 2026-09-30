def joined_text(runs: list) -> str:
    return "".join(run.text for run in runs)


def replace_in_runs(runs: list, find: str, replace: str) -> int:
    count = 0
    search_start = 0
    while True:
        position = joined_text(runs).find(find, search_start)
        if position < 0:
            return count
        replace_span(runs, position, position + len(find), replace)
        search_start = position + len(replace)
        count += 1


def replace_span(runs: list, start: int, end: int, replace: str) -> None:
    offset = 0
    replacement_written = False
    for run in runs:
        text = run.text
        run_start, run_end = offset, offset + len(text)
        offset = run_end
        if run_end <= start or run_start >= end:
            continue
        keep_before = text[:max(0, start - run_start)]
        keep_after = text[max(0, end - run_start):] if end < run_end else ""
        run.text = keep_before + ("" if replacement_written else replace) + keep_after
        replacement_written = True
