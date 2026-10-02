from __future__ import annotations

import io

from core.office_operations import OperationSet
from powerpoint.operations.arrangement import ARRANGEMENT_PLANNERS
from powerpoint.operations.chart_insert import CHART_INSERT_PLANNERS
from powerpoint.operations.comments import COMMENT_PLANNERS
from powerpoint.operations.presentation import DECK_PLANNERS
from powerpoint.definitions import OPERATIONS
from powerpoint.operations.elements import ELEMENT_PLANNERS
from powerpoint.operations.footers import FOOTER_PLANNERS
from powerpoint.operations.insert import INSERT_PLANNERS
from powerpoint.model.lengths import normalized_operation
from powerpoint.operations.links import LINK_PLANNERS
from powerpoint.operations.package_fidelity import preserve_unchanged_parts
from powerpoint.operations.sections import SECTION_PLANNERS
from powerpoint.model.sections import normalize_sections
from powerpoint.operations.show import SHOW_PLANNERS
from powerpoint.operations.slides import SLIDE_PLANNERS
from powerpoint.operations.table_format import TABLE_FORMAT_PLANNERS
from powerpoint.operations.tables import TABLE_AND_CHART_PLANNERS
from powerpoint.operations.targets import PptxEditing
from powerpoint.operations.text import TEXT_PLANNERS


def save_editing(editing: PptxEditing, path: str) -> None:
    normalize_sections(editing)
    rewritten = io.BytesIO()
    editing.presentation.save(rewritten)
    with open(path, "wb") as output:
        output.write(preserve_unchanged_parts(editing.original_package, rewritten.getvalue()))


def operation_in_emu(editing: PptxEditing, operation: dict, index: int) -> dict:
    slide_size = (editing.presentation.slide_width, editing.presentation.slide_height)
    return normalized_operation(OPERATIONS, operation, index, slide_size)


PPTX_OPERATIONS = OperationSet(OPERATIONS, {
    **TEXT_PLANNERS,
    **ELEMENT_PLANNERS,
    **ARRANGEMENT_PLANNERS,
    **LINK_PLANNERS,
    **INSERT_PLANNERS,
    **CHART_INSERT_PLANNERS,
    **TABLE_AND_CHART_PLANNERS,
    **TABLE_FORMAT_PLANNERS,
    **SLIDE_PLANNERS,
    **SHOW_PLANNERS,
    **COMMENT_PLANNERS,
    **FOOTER_PLANNERS,
    **SECTION_PLANNERS,
    **DECK_PLANNERS,
}, prepare=operation_in_emu)
