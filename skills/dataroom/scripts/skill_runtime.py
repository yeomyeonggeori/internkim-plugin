#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


SKILL_CACHE_DIRECTORY_NAME = "internkim-skills"
PREPARED_CACHE_HOME = Path(__file__).resolve().parents[2] / ".prepared"


class PreparationFailed(Exception):
    pass


def ensure_requirements(skill_name):
    requirements_path = requirements_file()
    if not has_requirements(requirements_path):
        return True
    environment_path = dependency_environment_path(skill_name)
    if is_running_in(environment_path):
        return True
    if not is_prepared(environment_path, requirements_path):
        return False
    reexecute_python(environment_path / "bin" / "python")
    return False


def prepare_requirements(skill_name):
    requirements_path = requirements_file()
    environment_path = dependency_environment_path(skill_name)
    if not has_requirements(requirements_path) or is_prepared(environment_path, requirements_path):
        return False
    python_path = environment_path / "bin" / "python"
    create_dependency_environment(python_path, environment_path)
    install_requirements_if_needed(python_path, requirements_path, environment_path)
    return True


def requirements_file():
    return Path(__file__).with_name("requirements.txt")


def has_requirements(requirements_path):
    return requirements_path.exists() and requirements_path.read_text(encoding="utf-8").strip() != ""


def is_prepared(environment_path, requirements_path, *options):
    return (environment_path / "bin" / "python").exists() and requirements_marker(environment_path, requirements_path, *options).exists()


def reexecute_python(python_path):
    os.execve(
        str(python_path),
        [str(python_path), str(Path(sys.argv[0]).resolve()), *sys.argv[1:]],
        os.environ.copy(),
    )


def create_dependency_environment(python_path, environment_path):
    if python_path.exists():
        return
    run_uv(["uv", "venv", "--python", sys.executable, str(environment_path)], "uv venv failed")


def install_requirements_if_needed(python_path, requirements_path, environment_path, *options):
    marker_path = requirements_marker(environment_path, requirements_path, *options)
    if marker_path.exists():
        return
    install_requirements(python_path, requirements_path, *options)
    marker_path.write_text("ok\n", encoding="utf-8")


def requirements_marker(environment_path, requirements_path, *options):
    return environment_path / f".requirements-{requirements_hash(requirements_path, *options)}.installed"


def requirements_hash(requirements_path, *options):
    digest = hashlib.sha256(requirements_path.read_bytes())
    for option in options:
        digest.update(b"\0" + (Path(option).read_bytes() if Path(option).is_file() else option.encode()))
    return digest.hexdigest()[:16]


def install_requirements(python_path, requirements_path, *options):
    run_uv(
        ["uv", "pip", "install", "--quiet", "--compile-bytecode", "--python", str(python_path), "-r", str(requirements_path), *options],
        "uv pip install failed",
    )


def run_uv(command, failure_message):
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=uv_environment(), check=False)
    except FileNotFoundError as error:
        raise PreparationFailed("uv is not on PATH") from error
    if result.returncode != 0:
        raise PreparationFailed((result.stderr or result.stdout or failure_message).strip())


def uv_environment():
    environment = os.environ.copy()
    environment["UV_CACHE_DIR"] = str(usable_uv_cache_path(environment))
    environment["UV_LINK_MODE"] = "copy"
    return environment


def usable_uv_cache_path(environment):
    configured_cache = environment.get("UV_CACHE_DIR", "").strip()
    candidates = [Path(configured_cache)] if configured_cache else []
    for candidate in [*candidates, skill_cache_path(environment) / "uv"]:
        if is_writable_directory(candidate):
            return candidate
    raise PreparationFailed("neither UV_CACHE_DIR nor the skill cache is a writable directory for uv's package cache")


def is_writable_directory(path):
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return os.access(path, os.W_OK)


def dependency_environment_path(skill_name):
    return skill_cache_path(os.environ) / "environments" / safe_name(skill_name)


def skill_cache_path(environment):
    return cache_home_path(environment) / SKILL_CACHE_DIRECTORY_NAME


def writable_skill_cache_path(environment):
    return writable_cache_home_path(environment) / SKILL_CACHE_DIRECTORY_NAME


def cache_home_path(environment):
    if PREPARED_CACHE_HOME.is_dir():
        return PREPARED_CACHE_HOME
    return writable_cache_home_path(environment)


def writable_cache_home_path(environment):
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


def setup_command():
    return f"python3 {Path(__file__).resolve()} setup"


def setup_envelope(skill_name):
    try:
        prepared = prepare_requirements(skill_name)
    except PreparationFailed as reason:
        issue = {
            "code": "DEPENDENCIES_UNAVAILABLE",
            "severity": "error",
            "message": f"{skill_name}: the Python packages could not be prepared: {reason}",
            "location": str(requirements_file()),
            "suggestion": "put uv on PATH and allow network access, then rerun setup",
        }
        return {"status": "error", "summary": f"{skill_name} is not prepared", "issues": [issue]}, 1
    step = {"name": "python environment", "state": "prepared" if prepared else "found", "path": str(dependency_environment_path(skill_name))}
    return {"status": "ok", "summary": f"{skill_name} is ready", "issues": [], "details": {"steps": [step]}}, 0


def print_envelope(envelope, stream):
    print(json.dumps(envelope, ensure_ascii=False, indent=2), file=stream)


def main():
    skill_name = Path(__file__).parents[1].name
    if sys.argv[1:2] == ["setup"]:
        envelope, exit_code = setup_envelope(skill_name)
        print_envelope(envelope, sys.stdout)
        sys.exit(exit_code)
    if len(sys.argv) < 3 or sys.argv[1] != "python":
        print("usage: skill_runtime.py setup\n       skill_runtime.py python <script.py> [args...]", file=sys.stderr)
        sys.exit(2)
    envelope, exit_code = setup_envelope(skill_name)
    if exit_code != 0:
        print_envelope(envelope, sys.stderr)
        sys.exit(exit_code)
    if not ensure_requirements(skill_name):
        sys.exit(1)
    os.execv(sys.executable, [sys.executable, *sys.argv[2:]])


if __name__ == "__main__":
    main()
