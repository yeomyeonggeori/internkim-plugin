from __future__ import annotations

import json
from pathlib import Path

from core.office_result import MISSING_FIELD, WRONG_TYPE, OfficeFailure


COMPANY_PROFILE_FILE = "company-profile.json"
COMPANY_IMAGES = (("sealImage", "stampPath"), ("logoImage", "logoPath"))
ANSWERED_BY = f"call company_info_get for the document's language and pass the path of the {COMPANY_PROFILE_FILE} its answer links to"


def with_company_profile(document: dict) -> dict:
    path = Path(str(document.get("company") or "")).expanduser()
    if not path.is_file():
        raise OfficeFailure(MISSING_FIELD.issue(f"values.company: no company profile at {path.resolve()}", "values.company", suggestion=ANSWERED_BY))
    profile = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise OfficeFailure(WRONG_TYPE.issue(f"values.company: {path} holds no company profile object", "values.company", suggestion=ANSWERED_BY))
    return document | {"profile": profile | image_paths(profile, path.parent)}


def image_paths(profile: dict, directory: Path) -> dict:
    paths = {}
    for answered_field, printed_field in COMPANY_IMAGES:
        name = str(profile.get(answered_field) or "").strip()
        if name:
            paths[printed_field] = str(directory / Path(name).name)
    return paths
