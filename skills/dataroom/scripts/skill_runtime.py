#!/usr/bin/env python3
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys


BOOTSTRAP_DISABLE_ENVIRONMENT_PREFIX = "INTERNKIM_SKILL_BOOTSTRAP_DISABLE"
SKILL_CACHE_DIRECTORY_NAME = "internkim-skills"


def ensure_requirements(skill_name):
    requirements_path = Path(__file__).with_name("requirements.txt")
    if not requirements_path.exists() or requirements_path.read_text(encoding="utf-8").strip() == "":
        return True
    if os.environ.get(bootstrap_disable_environment_variable(skill_name)) == "1":
        return False
    environment_path = dependency_environment_path(skill_name)
    python_path = environment_path / "bin" / "python"
    if is_running_in(environment_path):
        return True

    try:
        create_dependency_environment(python_path, environment_path)
        install_requirements_if_needed(python_path, requirements_path, environment_path)
    except Exception as error_value:
        sys.stderr.write(f"warning: {skill_name} dependency bootstrap failed: {error_value}\n")
        return False

    reexecute_python(python_path)
    return False


def reexecute_python(python_path):
    os.execve(
        str(python_path),
        [str(python_path), str(Path(sys.argv[0]).resolve()), *sys.argv[1:]],
        os.environ.copy(),
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


def install_requirements_if_needed(python_path, requirements_path, environment_path, *options):
    marker_path = environment_path / f".requirements-{requirements_hash(requirements_path)}.installed"
    if marker_path.exists():
        return
    install_requirements(python_path, requirements_path, *options)
    marker_path.write_text("ok\n", encoding="utf-8")


def requirements_hash(requirements_path):
    return hashlib.sha256(requirements_path.read_bytes()).hexdigest()[:16]


def install_requirements(python_path, requirements_path, *options):
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
            *options,
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


def is_running_in(environment_path):
    return Path(sys.prefix).resolve() == environment_path.resolve()


def safe_name(value):
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    if normalized == "":
        return "default"
    return normalized.lower()


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
