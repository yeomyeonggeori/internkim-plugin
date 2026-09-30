from __future__ import annotations

from pptx.enum.shapes import MSO_SHAPE_TYPE


def text_frames_in(shapes) -> list:
    frames = []
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            frames.extend(text_frames_in(shape.shapes))
        elif shape.has_table:
            frames.extend(cell.text_frame for row in shape.table.rows for cell in row.cells)
        elif shape.has_text_frame:
            frames.append(shape.text_frame)
    return frames


def frame_text(text_frame) -> str:
    return text_frame.text.replace("\v", "\n")


def shape_kind(shape) -> str:
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        return "group"
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        return "picture"
    if shape.has_table:
        return "table"
    if shape.has_text_frame:
        return "placeholder" if shape.is_placeholder else "text"
    return "shape"


def notes_text(slide) -> str:
    return frame_text(slide.notes_slide.notes_text_frame) if slide.has_notes_slide else ""
