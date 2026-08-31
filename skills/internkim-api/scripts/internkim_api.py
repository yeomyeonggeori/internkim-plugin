#!/usr/bin/env python3
"""Call the internkim public API, discovering its tools at run time."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://api.intern.kim/v1"
USER_AGENT = "internkim-api-skill/1.0"


def fail(message):
    print(json.dumps({"status": "error", "message": message}, ensure_ascii=False))
    sys.exit(1)


def resolve_token():
    token = os.environ.get("INTERNKIM_TOKEN", "").strip()
    if not token:
        fail("INTERNKIM_TOKEN is not set; run scripts/store_token.sh to keep one in this computer's secret store")
    return token


def resolve_base_url():
    return (os.environ.get("INTERNKIM_API_URL") or DEFAULT_BASE_URL).rstrip("/")


def request_json(path, payload=None):
    request = urllib.request.Request(
        f"{resolve_base_url()}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {resolve_token()}",
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


def tool_catalog():
    return request_json("/tools").get("tools", [])


def print_tool_list():
    for tool in tool_catalog():
        state = tool.get("availability", {}).get("state", "")
        description = " ".join(str(tool.get("description", "")).split())
        marker = "" if state == "ok" else f" [{state}]"
        print(f"{tool.get('canonicalName')}{marker}: {description}")


def print_tool_schema(name):
    for tool in tool_catalog():
        if tool.get("canonicalName") == name:
            print(json.dumps(tool, ensure_ascii=False, indent=2))
            return
    fail(f"no tool named {name}; run `tools` to see what this token may call")


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("tools")
    schema = subcommands.add_parser("schema")
    schema.add_argument("name")
    call = subcommands.add_parser("call")
    call.add_argument("name")
    call.add_argument("--input")
    arguments = parser.parse_args()

    if arguments.command == "tools":
        print_tool_list()
        return
    if arguments.command == "schema":
        print_tool_schema(arguments.name)
        return
    answer = request_json(f"/tools/{arguments.name}/invoke", {"input": read_input(arguments.input)})
    print(json.dumps(answer, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
