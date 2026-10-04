from __future__ import annotations

from schemas.known_values import load_runtime_context


def with_company_profile(document: dict, language: str) -> dict:
    context = load_runtime_context()
    return document | {"profile": context.company(language) if context is not None else {}}
