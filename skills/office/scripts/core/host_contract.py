from __future__ import annotations

import json

from core.skill_paths import ASSETS_PATH


HOST_CONTRACT = json.loads((ASSETS_PATH / "host-contract.json").read_text(encoding="utf-8"))
SOURCE_SUFFIX = HOST_CONTRACT["sourceSuffix"]
DELIVERABLE_EXTENSIONS = tuple(HOST_CONTRACT["deliverableExtensions"])
RUNTIME_CONTEXT_VARIABLE = HOST_CONTRACT["runtimeContextVariable"]
