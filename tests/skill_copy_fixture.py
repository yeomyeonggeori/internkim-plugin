from pathlib import Path
import shutil

from doc_fixture import SCRIPTS_PATH
from core.office_setup import setup_steps


SKILL_PATH = SCRIPTS_PATH.parent
PREPARED_LOCATIONS = {step.name: step.location.relative_to(SKILL_PATH) for step in setup_steps()}


def copy_skill(destination: Path, linked_pieces: tuple[str, ...] = ()) -> Path:
    prepared_names = {location.name for location in PREPARED_LOCATIONS.values()}
    shutil.copytree(SKILL_PATH, destination, ignore=shutil.ignore_patterns("__pycache__", *prepared_names))
    for name in linked_pieces:
        location = PREPARED_LOCATIONS[name]
        (destination / location).symlink_to(SKILL_PATH / location, target_is_directory=True)
    return destination / "scripts" / "office"
