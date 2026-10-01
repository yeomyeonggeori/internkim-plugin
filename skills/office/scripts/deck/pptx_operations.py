from __future__ import annotations

import io

from core.office_operations import OperationSet
from deck.pptx_arrangement_operations import ARRANGEMENT_PLANNERS
from deck.pptx_chart_insert import CHART_INSERT_PLANNERS
from deck.pptx_comments import COMMENT_PLANNERS
from deck.pptx_deck_operations import DECK_PLANNERS
from deck.pptx_edit_definitions import OPERATIONS
from deck.pptx_element_operations import ELEMENT_PLANNERS
from deck.pptx_footer_operations import FOOTER_PLANNERS
from deck.pptx_insert_operations import INSERT_PLANNERS
from deck.pptx_lengths import normalized_operation
from deck.pptx_link_operations import LINK_PLANNERS
from deck.pptx_package_fidelity import preserve_unchanged_parts
from deck.pptx_section_operations import SECTION_PLANNERS
from deck.pptx_sections import normalize_sections
from deck.pptx_show_operations import SHOW_PLANNERS
from deck.pptx_slide_operations import SLIDE_PLANNERS
from deck.pptx_table_format_operations import TABLE_FORMAT_PLANNERS
from deck.pptx_table_operations import TABLE_AND_CHART_PLANNERS
from deck.pptx_targets import PptxEditing
from deck.pptx_text_operations import TEXT_PLANNERS


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
