from pathlib import Path
import json
import os
import subprocess
import sys

SCRIPTS_PATH = Path(os.environ.get("OFFICE_SCRIPTS_PATH") or Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts")
OFFICE_ENTRY = SCRIPTS_PATH / "office"

CLEAN_TOKENS = {
    "intent": "a calm investor update: white ground, one blue accent, Pretendard throughout",
    "colors": {"ground": "#FFFFFF", "text": "#14213D", "accent": "#1F5FBF", "secondary": "#0F766E"},
    "fonts": {"display": "Pretendard", "body": "Pretendard"},
    "type": {"display": "64px", "title": "48px", "body": "24px"},
    "radius": "10px",
    "border": "1px",
    "shadow": "none",
    "spacing": {"margin": "96px", "gap": "32px"},
}


def design_markdown(overrides: dict | None = None) -> str:
    tokens = json.loads(json.dumps(CLEAN_TOKENS))
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(tokens.get(key), dict):
            tokens[key].update(value)
            tokens[key] = {name: entry for name, entry in tokens[key].items() if entry is not None}
        elif isinstance(value, dict):
            tokens[key] = value
        elif value is None:
            tokens.pop(key, None)
        else:
            tokens[key] = value
    lines = ["---"]
    for key, value in tokens.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            lines.extend(f'  {name}: "{entry}"' for name, entry in value.items())
        else:
            lines.append(f'{key}: "{value}"')
    lines.append("---")
    return "\n".join(lines) + "\n"


def run_office(arguments: list[str], working_directory: Path) -> dict:
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=working_directory)
    return json.loads(completed.stdout)


def issue_codes(envelope: dict) -> set[str]:
    return {issue["code"] for issue in envelope["issues"]}


def issues_at(envelope: dict, code: str) -> list[dict]:
    return [issue for issue in envelope["issues"] if issue["code"] == code]
