#!/usr/bin/env python3
"""Run every tests/test_*.py module in its own process, several at a time.

    python tests/run_parallel.py [--jobs N] [--python PATH] [module ...]

Exit status is 0 when every module passes. Failures are summarised at the end
with the tail of each failing module's output.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TESTS_DIRECTORY = Path(__file__).resolve().parent
VENV_PYTHON = TESTS_DIRECTORY.parent / "skills" / "office" / "scripts" / ".venv" / "bin" / "python"
SUMMARY_TAIL_LINES = 25


def modules_to_run(names: list[str]) -> list[str]:
    if names:
        return [name.removesuffix(".py") for name in names]
    return sorted(path.stem for path in TESTS_DIRECTORY.glob("test_*.py"))


def run_module(python: str, module: str) -> tuple[str, int, float, str]:
    started = time.monotonic()
    completed = subprocess.run([python, "-m", "unittest", module], cwd=TESTS_DIRECTORY, capture_output=True, text=True)
    return module, completed.returncode, time.monotonic() - started, completed.stderr + completed.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=max(2, (os.cpu_count() or 4) // 4))
    parser.add_argument("--python", default=str(VENV_PYTHON if VENV_PYTHON.exists() else sys.executable))
    parser.add_argument("modules", nargs="*")
    arguments = parser.parse_args()
    modules = modules_to_run(arguments.modules)
    started = time.monotonic()
    failed = []
    with ThreadPoolExecutor(max_workers=arguments.jobs) as pool:
        for module, code, seconds, output in pool.map(lambda name: run_module(arguments.python, name), modules):
            print(f"{'ok  ' if code == 0 else 'FAIL'} {module} ({seconds:.0f}s)", flush=True)
            if code != 0:
                failed.append((module, output))
    for module, output in failed:
        print(f"\n=== {module} ===\n" + "\n".join(output.splitlines()[-SUMMARY_TAIL_LINES:]))
    print(f"\n{len(modules) - len(failed)} of {len(modules)} modules passed in {time.monotonic() - started:.0f}s with {arguments.jobs} jobs")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
