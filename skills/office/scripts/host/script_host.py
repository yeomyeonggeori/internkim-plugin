from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
import urllib.error
import urllib.parse
import urllib.request


URL_VARIABLE = "SKILL_HOST_URL"
TOKEN_VARIABLE = "SKILL_HOST_TOKEN"
REQUEST_TIMEOUT_SECONDS = 300
MODEL_MISSING_STATUS = 501


class HostUnavailable(Exception):
    pass


class HostFailure(Exception):
    pass


@dataclass(frozen=True)
class Image:
    media_type: str
    data: bytes

    def to_json(self) -> dict:
        return {"mediaType": self.media_type, "data": base64.b64encode(self.data).decode("ascii")}


def is_present() -> bool:
    return bool(os.environ.get(URL_VARIABLE, "").strip() and os.environ.get(TOKEN_VARIABLE, "").strip())


def choice_question(instructions: str, options: dict[str, str]) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": options}


def decide(state: object, questions: dict[str, dict], images: list[Image] | None = None) -> dict:
    body = {"state": state, "questions": questions} | ({"images": [image.to_json() for image in images]} if images else {})
    return post("decide", body)


def generate(prompt: str, schema: dict, system: str = "", images: list[Image] | None = None) -> dict:
    body = {"system": system, "prompt": prompt, "schema": schema, "images": [image.to_json() for image in images or []]}
    return post("generate", body)


def call_tool(name: str, tool_input: dict) -> dict:
    return post("tools/" + urllib.parse.quote(name, safe=""), tool_input)


def post(route: str, body: dict) -> dict:
    if not is_present():
        raise HostUnavailable("this command runs on a host that offers no script host")
    request = urllib.request.Request(
        os.environ[URL_VARIABLE].rstrip("/") + "/" + route,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + os.environ[TOKEN_VARIABLE].strip(), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise answered_failure(route, error) from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise HostFailure(f"the script host did not answer {route}: {error}") from error


def answered_failure(route: str, error: urllib.error.HTTPError) -> Exception:
    with error:
        detail = error.read().decode("utf-8", errors="replace").strip()
    try:
        detail = str(json.loads(detail).get("error") or detail)
    except (json.JSONDecodeError, AttributeError):
        pass
    if error.code == MODEL_MISSING_STATUS:
        return HostUnavailable(f"{route}: {detail}")
    return HostFailure(f"{route} answered {error.code}: {detail}")


def cost_of(answer: dict) -> float:
    usage = answer.get("usage") or {}
    return float(usage.get("costUSD") or 0.0)
