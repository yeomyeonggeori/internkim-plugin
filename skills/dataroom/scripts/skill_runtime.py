#!/usr/bin/env python3
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys


BOOTSTRAP_READY_ENVIRONMENT_PREFIX = "INTERNKIM_SKILL_BOOTSTRAP_READY"
BOOTSTRAP_DISABLE_ENVIRONMENT_PREFIX = "INTERNKIM_SKILL_BOOTSTRAP_DISABLE"
SKILL_CACHE_DIRECTORY_NAME = "internkim-skills"

# Debian's fonts-nanum installs the first, the internkim package carries the
# second, fonts-noto-cjk installs the third, and older layouts the fourth; macOS
# carries the fifth. AppleGothic.ttf is deliberately
# absent: it is a legacy AAT face with no OS/2 table, so fpdf2's add_font raises
# KeyError: 'OS/2' and a host holding only that font has no Korean font at all.
HANGUL_FONT_PATHS = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/internkim/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]

# Debian's fonts-nanum installs NanumGothicBold.ttf beside NanumGothic.ttf and
# fonts-noto-cjk installs NotoSansCJK-Bold.ttc beside the Regular one, so a bold
# face is found by name next to its regular file. Apple SD Gothic Neo keeps all
# weights in one collection, where face 6 is Bold.
HANGUL_BOLD_COLLECTION_FACES = {
    "/System/Library/Fonts/AppleSDGothicNeo.ttc": 6,
}


def find_bold_face(regular_font_path):
    regular_path = Path(regular_font_path)
    collection_face = HANGUL_BOLD_COLLECTION_FACES.get(str(regular_path))
    if collection_face is not None and regular_path.exists():
        return regular_path, collection_face
    for bold_path in bold_sibling_paths(regular_path):
        if bold_path.exists():
            return bold_path, 0
    return None


def bold_sibling_paths(regular_path):
    stem = regular_path.stem
    bold_stems = [f"{stem}Bold", f"{stem}-Bold"]
    if "Regular" in stem:
        bold_stems.insert(0, stem.replace("Regular", "Bold"))
    return [regular_path.with_name(bold_stem + regular_path.suffix) for bold_stem in bold_stems]


def ensure_requirements(skill_name):
    requirements_path = Path(__file__).with_name("requirements.txt")
    if not requirements_path.exists() or requirements_path.read_text(encoding="utf-8").strip() == "":
        return True
    if os.environ.get(bootstrap_disable_environment_variable(skill_name)) == "1":
        return False
    if os.environ.get(bootstrap_ready_environment_variable(skill_name)) == "1":
        return True

    if python_satisfies_requirements(Path(sys.executable), requirements_path):
        return True

    environment_path = dependency_environment_path(skill_name)
    python_path = environment_path / "bin" / "python"
    try:
        create_dependency_environment(python_path, environment_path)
        install_requirements_if_needed(python_path, requirements_path, environment_path)
    except Exception as error_value:
        sys.stderr.write(f"warning: {skill_name} dependency bootstrap failed: {error_value}\n")
        return False

    if is_current_python(python_path):
        return True

    reexecute_python(python_path, skill_name)
    return False


def python_satisfies_requirements(python_path, requirements_path):
    code = """
import importlib.metadata
import re
import sys
from pathlib import Path

for raw_requirement in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    requirement = raw_requirement.split("#", 1)[0].strip()
    if requirement == "":
        continue
    package_name = re.split(r"\\s*(?:==|>=|<=|~=|!=|>|<|\\[|;)", requirement, 1)[0].strip()
    if package_name == "":
        continue
    try:
        importlib.metadata.distribution(package_name)
    except importlib.metadata.PackageNotFoundError:
        sys.exit(1)
"""
    result = subprocess.run(
        [str(python_path), "-c", code, str(requirements_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def reexecute_python(python_path, skill_name):
    environment = os.environ.copy()
    environment[bootstrap_ready_environment_variable(skill_name)] = "1"
    os.execve(
        str(python_path),
        [str(python_path), str(Path(sys.argv[0]).resolve()), *sys.argv[1:]],
        environment,
    )


def create_dependency_environment(python_path, environment_path):
    if python_path.exists():
        return
    result = subprocess.run(
        ["uv", "venv", "--python", sys.executable, str(environment_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=uv_environment(),
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "uv venv failed").strip()
        raise RuntimeError(message)


def install_requirements_if_needed(python_path, requirements_path, environment_path):
    marker_path = environment_path / f".requirements-{requirements_hash(requirements_path)}.installed"
    if marker_path.exists():
        return
    install_requirements(python_path, requirements_path)
    marker_path.write_text("ok\n", encoding="utf-8")


def requirements_hash(requirements_path):
    return hashlib.sha256(requirements_path.read_bytes()).hexdigest()[:16]


def install_requirements(python_path, requirements_path):
    result = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--quiet",
            "--python",
            str(python_path),
            "-r",
            str(requirements_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=uv_environment(),
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "uv pip install failed").strip()
        raise RuntimeError(message)


def uv_environment():
    environment = os.environ.copy()
    dependency_cache = uv_cache_path(environment)
    dependency_cache.mkdir(parents=True, exist_ok=True)
    environment["UV_CACHE_DIR"] = str(dependency_cache)
    environment["UV_LINK_MODE"] = "copy"
    return environment


def uv_cache_path(environment):
    configured_cache = environment.get("UV_CACHE_DIR", "").strip()
    if configured_cache != "":
        return Path(configured_cache)
    return skill_cache_path(environment) / "uv"


def dependency_environment_path(skill_name):
    return skill_cache_path(os.environ) / "environments" / safe_name(skill_name)


def skill_cache_path(environment):
    return cache_home_path(environment) / SKILL_CACHE_DIRECTORY_NAME


def cache_home_path(environment):
    configured_cache_home = environment.get("XDG_CACHE_HOME", "").strip()
    if configured_cache_home != "":
        return Path(configured_cache_home)
    return Path.home() / ".cache"


def is_current_python(python_path):
    return Path(sys.executable).absolute() == python_path.absolute()


def safe_name(value):
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    if normalized == "":
        return "default"
    return normalized.lower()


def bootstrap_ready_environment_variable(skill_name):
    return f"{BOOTSTRAP_READY_ENVIRONMENT_PREFIX}_{environment_suffix(skill_name)}"


def bootstrap_disable_environment_variable(skill_name):
    return f"{BOOTSTRAP_DISABLE_ENVIRONMENT_PREFIX}_{environment_suffix(skill_name)}"


def environment_suffix(skill_name):
    normalized = re.sub(r"[^A-Z0-9]+", "_", skill_name.upper()).strip("_")
    if normalized == "":
        return "DEFAULT"
    return normalized


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "python":
        print("usage: skill_runtime.py python <script.py> [args...]", file=sys.stderr)
        sys.exit(2)
    skill_name = Path(__file__).parents[1].name
    if not ensure_requirements(skill_name):
        sys.exit(1)
    os.execv(sys.executable, [sys.executable, *sys.argv[2:]])


if __name__ == "__main__":
    main()
