#!/usr/bin/env python3
"""Call the internkim public API, discovering its tools at run time."""

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://api.intern.kim/v1"
USER_AGENT = "internkim-api-skill/1.0"
CONFIGURATION_PATHS = ("~/.internkim/api.json", "~/.config/internkim/api.json")


def configuration_file_values():
    for candidate in CONFIGURATION_PATHS:
        path = pathlib.Path(candidate).expanduser()
        if not path.is_file():
            continue
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            fail(f"{path} is not valid JSON")
    return {}


def resolve_credentials(base_url_argument):
    values = configuration_file_values()
    token = os.environ.get("INTERNKIM_TOKEN", "").strip()
    if not token:
        token_file = os.environ.get("INTERNKIM_TOKEN_FILE", "").strip()
        if token_file:
            token = pathlib.Path(token_file).expanduser().read_text().strip()
    if not token:
        token = str(values.get("token", "")).strip()
    if not token:
        fail("no API token: set INTERNKIM_TOKEN, or put {\"token\": \"ik_...\"} in ~/.internkim/api.json")
    base_url = base_url_argument or os.environ.get("INTERNKIM_API_URL") or values.get("baseURL") or DEFAULT_BASE_URL
    return str(base_url).rstrip("/"), token


def fail(message):
    print(json.dumps({"status": "error", "message": message}, ensure_ascii=False))
    sys.exit(1)


def request_json(base_url, token, path, payload=None):
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace").strip()
        fail(f"{path} answered {error.code}: {body[:400]}")
    except urllib.error.URLError as error:
        fail(f"{path} could not be reached: {error.reason}")


def tool_catalog(base_url, token):
    return request_json(base_url, token, "/tools").get("tools", [])


def print_tool_list(base_url, token):
    for tool in tool_catalog(base_url, token):
        state = tool.get("availability", {}).get("state", "")
        description = " ".join(str(tool.get("description", "")).split())
        marker = "" if state == "ok" else f" [{state}]"
        print(f"{tool.get('canonicalName')}{marker}: {description}")


def print_tool_schema(base_url, token, name):
    for tool in tool_catalog(base_url, token):
        if tool.get("canonicalName") == name:
            print(json.dumps(tool, ensure_ascii=False, indent=2))
            return
    fail(f"no tool named {name}; run `tools` to see what this key may call")


def read_input(input_argument):
    document = input_argument if input_argument is not None else sys.stdin.read()
    if not document.strip():
        return {}
    try:
        value = json.loads(document)
    except json.JSONDecodeError as error:
        fail(f"--input is not valid JSON: {error}")
    if not isinstance(value, dict):
        fail("--input must be a JSON object of the tool's own fields")
    return value


def call_tool(base_url, token, name, tool_input):
    answer = request_json(base_url, token, f"/tools/{name}/invoke", {"input": tool_input})
    print(json.dumps(answer, ensure_ascii=False, indent=2))
    return 0 if answer.get("outcome") == "succeeded" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("tools")
    schema = subcommands.add_parser("schema")
    schema.add_argument("name")
    call = subcommands.add_parser("call")
    call.add_argument("name")
    call.add_argument("--input")
    arguments = parser.parse_args()

    base_url, token = resolve_credentials(arguments.base_url)
    if arguments.command == "tools":
        print_tool_list(base_url, token)
        return 0
    if arguments.command == "schema":
        print_tool_schema(base_url, token, arguments.name)
        return 0
    return call_tool(base_url, token, arguments.name, read_input(arguments.input))


if __name__ == "__main__":
    sys.exit(main())
