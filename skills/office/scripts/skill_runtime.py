#!/usr/bin/env python3
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
ENVIRONMENT_DIRECTORY_NAME = ".venv"
REQUIREMENTS_FILE_NAME = "requirements.txt"
LOCK_FILE_NAME = "pylock.toml"
REQUIRES_PYTHON_PATTERN = re.compile(r'^requires-python = ">=(\d+)\.(\d+)"$', re.MULTILINE)


class PreparationFailed(Exception):
    pass


def ensure_requirements(directory=SCRIPTS_DIRECTORY):
    if not has_requirements(directory):
        return True
    if is_running_in(environment_path(directory)):
        return True
    if not is_prepared(directory):
        return False
    reexecute_python(environment_path(directory) / "bin" / "python")
    return False


def prepare_environment(directory=SCRIPTS_DIRECTORY):
    if not has_requirements(directory) or is_prepared(directory):
        return False
    lock = lock_path(directory)
    if not lock.exists():
        raise PreparationFailed(f"{lock} is missing; compile it from {REQUIREMENTS_FILE_NAME} with the command its header records")
    environment = environment_path(directory)
    if environment.exists():
        shutil.rmtree(environment)
    run_uv(["uv", "venv", "--quiet", "--python", interpreter_for(lock), str(environment)])
    run_uv(["uv", "pip", "sync", "--quiet", "--compile-bytecode", "--python", str(environment / "bin" / "python"), str(lock)])
    shutil.copyfile(lock, environment / LOCK_FILE_NAME)
    return True


def environment_path(directory=SCRIPTS_DIRECTORY):
    return directory / ENVIRONMENT_DIRECTORY_NAME


def lock_path(directory=SCRIPTS_DIRECTORY):
    return directory / LOCK_FILE_NAME


def has_requirements(directory):
    requirements = directory / REQUIREMENTS_FILE_NAME
    return requirements.exists() and requirements.read_text(encoding="utf-8").strip() != ""


def is_prepared(directory):
    environment = environment_path(directory)
    installed_lock = environment / LOCK_FILE_NAME
    lock = lock_path(directory)
    if not (environment / "bin" / "python").exists() or not installed_lock.exists() or not lock.exists():
        return False
    return installed_lock.read_bytes() == lock.read_bytes()


def interpreter_for(lock):
    match = REQUIRES_PYTHON_PATTERN.search(lock.read_text(encoding="utf-8"))
    if match is None or sys.version_info[:2] >= (int(match.group(1)), int(match.group(2))):
        return sys.executable
    return f">={match.group(1)}.{match.group(2)}"


def reexecute_python(python_path):
    os.execve(
        str(python_path),
        [str(python_path), str(Path(sys.argv[0]).resolve()), *sys.argv[1:]],
        os.environ.copy(),
    )


def run_uv(command):
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=uv_environment(os.environ), check=False)
    except FileNotFoundError as error:
        raise PreparationFailed("uv is not on PATH") from error
    if result.returncode != 0:
        raise PreparationFailed((result.stderr or result.stdout or f"{' '.join(command[:3])} failed").strip())


def uv_environment(environment):
    prepared = {**environment, "UV_LINK_MODE": "copy"}
    configured_cache = environment.get("UV_CACHE_DIR", "").strip()
    if configured_cache and not is_writable_directory(Path(configured_cache)):
        del prepared["UV_CACHE_DIR"]
    return prepared


def is_writable_directory(path):
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return os.access(path, os.W_OK)


def is_running_in(environment):
    return Path(sys.prefix).resolve() == environment.resolve()


def setup_command():
    return f"python3 {Path(__file__).resolve()} setup"


def setup_envelope():
    try:
        prepared = prepare_environment()
    except PreparationFailed as reason:
        issue = {
            "code": "SETUP_FAILED",
            "severity": "error",
            "message": f"the Python environment could not be prepared: {reason}",
            "location": "python environment",
            "suggestion": "put uv on PATH and allow network access, then rerun setup",
        }
        return {"status": "error", "summary": issue["message"], "issues": [issue], "details": {"steps": []}}, 1
    step = {"name": "python environment", "state": "prepared" if prepared else "found", "path": str(environment_path())}
    return {"status": "ok", "summary": f"{SCRIPTS_DIRECTORY.parent.name} is ready", "issues": [], "details": {"steps": [step]}}, 0


def print_envelope(envelope, stream):
    print(json.dumps(envelope, ensure_ascii=False, indent=2), file=stream)


def main():
    if sys.argv[1:2] == ["setup"]:
        envelope, exit_code = setup_envelope()
        print_envelope(envelope, sys.stdout)
        sys.exit(exit_code)
    if len(sys.argv) < 3 or sys.argv[1] != "python":
        print("usage: skill_runtime.py setup\n       skill_runtime.py python <script.py> [args...]", file=sys.stderr)
        sys.exit(2)
    if not ensure_requirements():
        print(f"error: the Python environment is not prepared; run {setup_command()} once", file=sys.stderr)
        sys.exit(1)
    os.execv(sys.executable, [sys.executable, *sys.argv[2:]])


if __name__ == "__main__":
    main()
