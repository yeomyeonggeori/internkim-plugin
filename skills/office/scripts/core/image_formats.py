from __future__ import annotations


OFFICE_PICTURE_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif", "BMP": "image/bmp", "TIFF": "image/tiff"}
WEB_IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml"}
OFFICE_PICTURE_FORMATS = tuple(OFFICE_PICTURE_TYPES)
OFFICE_PICTURE_CONTENT_TYPES = frozenset(OFFICE_PICTURE_TYPES.values())
WEB_IMAGE_CONTENT_TYPES = frozenset(WEB_IMAGE_TYPES.values())
PICTURE_FORMATS_TEXT = ", ".join(OFFICE_PICTURE_FORMATS[:-1]) + " or " + OFFICE_PICTURE_FORMATS[-1]
