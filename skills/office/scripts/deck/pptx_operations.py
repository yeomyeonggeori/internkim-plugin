from __future__ import annotations

import io

from office_operations import OperationSet
from pptx_deck_operations import DECK_PLANNERS
from pptx_edit_definitions import OPERATIONS
from pptx_element_operations import ELEMENT_PLANNERS
from pptx_insert_operations import INSERT_PLANNERS
from pptx_package_fidelity import preserve_unchanged_parts
from pptx_sections import normalize_sections
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
    **INSERT_PLANNERS,
    **TABLE_AND_CHART_PLANNERS,
    **SLIDE_PLANNERS,
    **DECK_PLANNERS,
})
