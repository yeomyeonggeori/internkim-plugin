from __future__ import annotations

from dataclasses import dataclass, field
import statistics


MINIMUM_ROWS = 2
MINIMUM_COLUMNS = 2
UNIT_GAP_EMS = 0.9
ROW_TOLERANCE_RATIO = 0.45
ROW_GAP_RATIO = 1.6
STRONG_ROW_UNITS = 5
PITCH_CONTINUATION_RATIO = 1.35
VALLEY_EMS = 0.4
ALIGN_TOLERANCE_EMS = 0.4
MINIMUM_ALIGNED_SHARE = 0.6
PARAGRAPH_FILL = 0.85
PROSE_WIDTH_EMS = 10
SENTENCE_WORDS = 5
FULL_ENTRY_SHARE = 0.5
PAGE_COVER_SHARE = 0.7
PAGE_COLUMN_WORDS = 4
PITCH_DEVIATION_SHARE = 0.2
MINIMUM_CONFIDENCE = 0.5
RULE_SPAN_SHARE = 0.5
ABSORBED_WIDTH_SHARE = 0.5
MAXIMUM_SPLIT_DEPTH = 2


@dataclass(frozen=True)
class Unit:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float

    @property
    def center(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass
class Row:
    units: list[Unit]

    @property
    def top(self) -> float:
        return min(unit.top for unit in self.units)

    @property
    def bottom(self) -> float:
        return max(unit.bottom for unit in self.units)

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def is_anchor(self) -> bool:
        return len(self.units) >= MINIMUM_COLUMNS


@dataclass
class Candidate:
    rows: list[Row]
    columns: list[tuple[float, float]]
    entries: list[list[list[Unit]]] = field(default_factory=list)

    @property
    def font_size(self) -> float:
        return statistics.median(unit.size for row in self.rows for unit in row.units)

    @property
    def box(self) -> tuple[float, float, float, float]:
        units = [unit for row in self.rows for unit in row.units]
        return (min(unit.x0 for unit in units), self.rows[0].top, max(unit.x1 for unit in units), self.rows[-1].bottom)


@dataclass(frozen=True)
class FoundTable:
    bbox: tuple[float, float, float, float]
    rows: list[list[str]]


def page_tables(page) -> list[FoundTable]:
    gridded = [table for table in (FoundTable(tuple(table.bbox), clean_rows(table.extract())) for table in page.find_tables()) if is_regular(table.rows)]
    boxes = [table.bbox for table in gridded]
    words = [word for word in page.extract_words(extra_attrs=["size"]) if not any(inside(word, box) for box in boxes)]
    return sorted(gridded + stream_tables(words, page.horizontal_edges), key=lambda table: table.bbox[1])


def clean_rows(rows: list[list]) -> list[list[str]]:
    return [[" ".join((cell or "").split()) for cell in row] for row in rows if any(cell for cell in row)]


def is_regular(rows: list[list[str]]) -> bool:
    return len(rows) >= 2 and max(len(row) for row in rows) >= 2


def inside(word: dict, box: tuple[float, float, float, float]) -> bool:
    left, top, right, bottom = box
    return left <= (word["x0"] + word["x1"]) / 2 <= right and top <= (word["top"] + word["bottom"]) / 2 <= bottom


def stream_tables(words: list[dict], rules: list[dict]) -> list[FoundTable]:
    rows = unit_rows(words)
    total_units = sum(len(row.units) for row in rows)
    candidates = [candidate for run in candidate_runs(rows) for candidate in solved_candidates(run, 0)]
    return [table_from(candidate) for candidate in candidates if is_table(candidate, total_units, rules)]


def line_texts(words: list[dict]) -> list[str]:
    return [" ".join(unit.text for unit in row.units) for row in unit_rows(words)]


def unit_rows(words: list[dict]) -> list[Row]:
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda word: (word["top"], word["x0"])):
        if lines and abs(lines[-1][0]["top"] - word["top"]) <= ROW_TOLERANCE_RATIO * word_size(word):
            lines[-1].append(word)
        else:
            lines.append([word])
    return [Row(line_units(sorted(line, key=lambda word: word["x0"]))) for line in lines]


def word_size(word: dict) -> float:
    return float(word.get("size") or word["bottom"] - word["top"])


def line_units(words: list[dict]) -> list[Unit]:
    groups = [[words[0]]]
    for word in words[1:]:
        previous = groups[-1][-1]
        if word["x0"] - previous["x1"] >= UNIT_GAP_EMS * max(word_size(previous), word_size(word)):
            groups.append([word])
        else:
            groups[-1].append(word)
    return [unit_from(group) for group in groups]


def unit_from(words: list[dict]) -> Unit:
    return Unit(
        text=" ".join(word["text"] for word in words),
        x0=min(word["x0"] for word in words),
        x1=max(word["x1"] for word in words),
        top=min(word["top"] for word in words),
        bottom=max(word["bottom"] for word in words),
        size=statistics.median(word_size(word) for word in words),
    )


def candidate_runs(rows: list[Row]) -> list[list[Row]]:
    runs: list[list[Row]] = []
    run: list[Row] = []
    for row in rows:
        follows = bool(run) and (row.top - run[-1].bottom <= ROW_GAP_RATIO * max(run[-1].height, row.height) or keeps_the_pitch(run, row))
        if row.is_anchor and (not run or follows):
            run.append(row)
        elif follows and continues_a_cell(run, row):
            run.append(row)
        else:
            runs.append(run)
            run = [row] if row.is_anchor else []
    runs.append(run)
    return [trimmed for trimmed in map(trimmed_run, runs) if anchor_count(trimmed) >= MINIMUM_ROWS]


def keeps_the_pitch(run: list[Row], row: Row) -> bool:
    anchors = [anchor for anchor in run if anchor.is_anchor]
    if len(anchors) < 2 or statistics.median(len(anchor.units) for anchor in anchors) < STRONG_ROW_UNITS:
        return False
    pitch = statistics.median(current.top - previous.top for previous, current in zip(run, run[1:]))
    return pitch > 0 and row.top - run[-1].top <= PITCH_CONTINUATION_RATIO * pitch


def continues_a_cell(run: list[Row], row: Row) -> bool:
    left = min(unit.x0 for anchor in run for unit in anchor.units)
    right = max(unit.x1 for anchor in run for unit in anchor.units)
    unit = row.units[0]
    return unit.x1 - unit.x0 <= ABSORBED_WIDTH_SHARE * (right - left) and left - unit.size <= unit.x0 and unit.x1 <= right + unit.size


def trimmed_run(run: list[Row]) -> list[Row]:
    first = next((index for index, row in enumerate(run) if row.is_anchor), len(run))
    last = max((index for index, row in enumerate(run) if row.is_anchor), default=-1)
    return run[first:last + 1]


def anchor_count(run: list[Row]) -> int:
    return sum(1 for row in run if row.is_anchor)


def solved_candidates(run: list[Row], depth: int) -> list[Candidate]:
    candidate = solved_columns(run)
    if candidate is not None and minimum_alignment(candidate) >= MINIMUM_ALIGNED_SHARE:
        return [candidate]
    if depth >= MAXIMUM_SPLIT_DEPTH or anchor_count(run) < 2 * MINIMUM_ROWS:
        return [candidate] if candidate is not None else []
    cut = widest_gap_index(run)
    halves = (trimmed_run(run[:cut]), trimmed_run(run[cut:]))
    return [piece for half in halves if anchor_count(half) >= MINIMUM_ROWS for piece in solved_candidates(half, depth + 1)]


def widest_gap_index(run: list[Row]) -> int:
    gaps = [(run[index].top - run[index - 1].bottom, index) for index in range(1, len(run))]
    return max(gaps)[1]


def solved_columns(run: list[Row]) -> Candidate | None:
    anchors = [unit for row in run if row.is_anchor for unit in row.units]
    font_size = statistics.median(unit.size for unit in anchors)
    columns = merged_intervals([(unit.x0, unit.x1) for unit in anchors], VALLEY_EMS * font_size)
    if len(columns) < MINIMUM_COLUMNS:
        return None
    candidate = Candidate(run, columns)
    candidate.entries = [[[] for _ in columns] for _ in run]
    for row_index, row in enumerate(run):
        for unit in row.units:
            candidate.entries[row_index][column_of(unit, columns)].append(unit)
    return candidate


def merged_intervals(intervals: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(intervals):
        if merged and start - merged[-1][1] < tolerance:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def column_of(unit: Unit, columns: list[tuple[float, float]]) -> int:
    return min(range(len(columns)), key=lambda index: distance_to(unit.center, columns[index]))


def distance_to(position: float, interval: tuple[float, float]) -> float:
    start, end = interval
    return max(start - position, 0, position - end)


def entry_boxes(candidate: Candidate, column: int) -> list[tuple[float, float]]:
    return [(min(unit.x0 for unit in units), max(unit.x1 for unit in units)) for units in (row[column] for row in candidate.entries) if units]


def alignment(candidate: Candidate, column: int) -> float:
    boxes = entry_boxes(candidate, column)
    if len(boxes) < 2:
        return 1.0
    tolerance = ALIGN_TOLERANCE_EMS * candidate.font_size
    edges = (lambda box: box[0], lambda box: box[1], lambda box: (box[0] + box[1]) / 2)
    return max(aligned_count([edge(box) for box in boxes], tolerance) for edge in edges) / len(boxes)


def aligned_count(positions: list[float], tolerance: float) -> int:
    middle = statistics.median(positions)
    return sum(1 for position in positions if abs(position - middle) <= tolerance)


def minimum_alignment(candidate: Candidate) -> float:
    return min(alignment(candidate, column) for column in range(len(candidate.columns)))


@dataclass(frozen=True)
class EntryShape:
    fill: float
    width_ems: float
    words: float
    full_share: float


def entry_shape(candidate: Candidate) -> EntryShape:
    measured = []
    for row in candidate.entries:
        for column, units in enumerate(row):
            if not units:
                continue
            start, end = candidate.columns[column]
            width = max(unit.x1 for unit in units) - min(unit.x0 for unit in units)
            measured.append((width / max(end - start, 1), width / candidate.font_size, sum(unit.word_count for unit in units)))
    if not measured:
        return EntryShape(0, 0, 0, 0)
    return EntryShape(
        fill=statistics.mean(fill for fill, _, _ in measured),
        width_ems=statistics.mean(width for _, width, _ in measured),
        words=statistics.mean(words for _, _, words in measured),
        full_share=sum(1 for fill, _, _ in measured if fill >= PARAGRAPH_FILL) / len(measured),
    )


def reads_as_prose(shape: EntryShape) -> bool:
    is_sentence_length = shape.width_ems >= PROSE_WIDTH_EMS or shape.words >= SENTENCE_WORDS
    return is_sentence_length and (shape.fill >= PARAGRAPH_FILL or shape.full_share >= FULL_ENTRY_SHARE)


def is_page_columns(candidate: Candidate, shape: EntryShape, total_units: int) -> bool:
    units = sum(len(row.units) for row in candidate.rows)
    if units / max(total_units, 1) < PAGE_COVER_SHARE or len(candidate.rows) < 3:
        return False
    pitches = [current.top - previous.top for previous, current in zip(candidate.rows, candidate.rows[1:])]
    pitch = statistics.median(pitches)
    deviation = statistics.median(abs(value - pitch) for value in pitches)
    if pitch <= 0 or deviation > PITCH_DEVIATION_SHARE * pitch:
        return False
    return shape.width_ems >= 0.8 * PROSE_WIDTH_EMS and shape.words >= PAGE_COLUMN_WORDS


def has_rule_evidence(candidate: Candidate, rules: list[dict]) -> bool:
    left, top, right, bottom = candidate.box
    row_height = statistics.median(row.height for row in candidate.rows)
    return any(
        top - row_height <= rule["top"] <= bottom + row_height
        and min(rule["x1"], right) - max(rule["x0"], left) >= RULE_SPAN_SHARE * (right - left)
        for rule in rules
    )


def confidence(candidate: Candidate, rules: list[dict]) -> float:
    rows = anchor_count(candidate.rows)
    score = 0.3
    if rows >= 3:
        score += 0.15 + min(0.1, 0.02 * (rows - 3))
    score += 0.15 * (minimum_alignment(candidate) - MINIMUM_ALIGNED_SHARE) / (1 - MINIMUM_ALIGNED_SHARE)
    if has_rule_evidence(candidate, rules):
        score += 0.2
    return score


def is_table(candidate: Candidate, total_units: int, rules: list[dict]) -> bool:
    if minimum_alignment(candidate) < MINIMUM_ALIGNED_SHARE:
        return False
    shape = entry_shape(candidate)
    if reads_as_prose(shape) or is_page_columns(candidate, shape, total_units):
        return False
    return confidence(candidate, rules) >= MINIMUM_CONFIDENCE


def table_from(candidate: Candidate) -> FoundTable:
    rows: list[list[str]] = []
    for row, entries in zip(candidate.rows, candidate.entries):
        cells = [" ".join(unit.text for unit in sorted(units, key=lambda unit: unit.x0)) for units in entries]
        if row.is_anchor or not rows:
            rows.append(cells)
        else:
            rows[-1] = [" ".join(part for part in (above, below) if part) for above, below in zip(rows[-1], cells)]
    return FoundTable(candidate.box, rows)
