#!/usr/bin/env python3
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys


BOOTSTRAP_READY_ENVIRONMENT_PREFIX = "INTERNKIM_SKILL_BOOTSTRAP_READY"
BOOTSTRAP_DISABLE_ENVIRONMENT_PREFIX = "INTERNKIM_SKILL_BOOTSTRAP_DISABLE"
BUILTIN_SKILLS_PYTHON_ENVIRONMENT = "BLUECLAW_BUILTIN_SKILLS_PYTHON"


def ensure_requirements(skill_name):
    requirements_path = Path(__file__).with_name("requirements.txt")
    if not requirements_path.exists() or requirements_path.read_text(encoding="utf-8").strip() == "":
        return True
    if os.environ.get(bootstrap_disable_environment_variable(skill_name)) == "1":
        return False
    if os.environ.get(bootstrap_ready_environment_variable(skill_name)) == "1":
        return True

    prepared_python = prepared_python_path(requirements_path)
    if prepared_python is not None:
        reexecute_python(prepared_python, skill_name)
        return False

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


def prepared_python_path(requirements_path):
    configured_python_path = os.environ.get(BUILTIN_SKILLS_PYTHON_ENVIRONMENT, "").strip()
    if configured_python_path == "":
        return None
    python_path = Path(configured_python_path)
    if not python_path.exists():
        return None
    if not python_satisfies_requirements(python_path, requirements_path):
        return None
    if is_current_python(python_path):
        return None
    return python_path


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
    configured_cache = environment.get("UV_CACHE_DIR")
    if configured_cache is not None and configured_cache.strip() != "":
        return Path(configured_cache)
    dependency_cache = environment.get("BLUECLAW_DEPENDENCY_CACHE")
    if dependency_cache is not None and dependency_cache.strip() != "":
        return Path(dependency_cache) / "uv"
    root = environment.get("BLUECLAW_REQUESTER_TMP")
    if root is None or root.strip() == "":
        root = environment.get("TMPDIR", "/tmp")
    return Path(root) / "internkim-skill-cache" / "uv"


def dependency_environment_path(skill_name):
    root = os.environ.get("BLUECLAW_REQUESTER_TMP")
    if root is None or root.strip() == "":
        root = str(Path.cwd())
    return Path(root) / ".skill-env" / safe_name(skill_name)


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
