from __future__ import annotations

import io

from office_operations import OperationSet
from pptx_arrangement_operations import ARRANGEMENT_PLANNERS
from pptx_comments import COMMENT_PLANNERS
from pptx_deck_operations import DECK_PLANNERS
from pptx_edit_definitions import OPERATIONS
from pptx_element_operations import ELEMENT_PLANNERS
from pptx_footer_operations import FOOTER_PLANNERS
from pptx_insert_operations import INSERT_PLANNERS
from pptx_link_operations import LINK_PLANNERS
from pptx_package_fidelity import preserve_unchanged_parts
from pptx_section_operations import SECTION_PLANNERS
from pptx_sections import normalize_sections
from pptx_show_operations import SHOW_PLANNERS
from pptx_slide_operations import SLIDE_PLANNERS
from pptx_table_operations import TABLE_AND_CHART_PLANNERS
from pptx_targets import PptxEditing
from pptx_text_operations import TEXT_PLANNERS


def save_editing(editing: PptxEditing, path: str) -> None:
    normalize_sections(editing)
    rewritten = io.BytesIO()
    editing.presentation.save(rewritten)
    with open(path, "wb") as output:
        output.write(preserve_unchanged_parts(editing.original_package, rewritten.getvalue()))


PPTX_OPERATIONS = OperationSet(OPERATIONS, {
    **TEXT_PLANNERS,
    **ELEMENT_PLANNERS,
    **ARRANGEMENT_PLANNERS,
    **LINK_PLANNERS,
    **INSERT_PLANNERS,
    **TABLE_AND_CHART_PLANNERS,
    **SLIDE_PLANNERS,
    **SHOW_PLANNERS,
    **COMMENT_PLANNERS,
    **FOOTER_PLANNERS,
    **SECTION_PLANNERS,
    **DECK_PLANNERS,
})
