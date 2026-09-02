#!/usr/bin/env python3
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request

def open_request(base_url: str, path: str, method: str = "GET", body: dict = None, token: str = "") -> tuple:
    headers = {}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if token:
        headers["Authorization"] = token
    request = urllib.request.Request(base_url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("Content-Type", ""), error.read()


def load_site_content(base_url: str, failures: list) -> dict:
    status, _, body = open_request(base_url, "/site-content.json")
    if status != 200:
        failures.append(f"site-content.json returned {status}")
        return {}
    try:
        return json.loads(body)
    except ValueError:
        failures.append("site-content.json is not valid JSON")
        return {}


def check_homepage(base_url: str, content: dict, failures: list):
    status, _, body = open_request(base_url, "/")
    if status != 200:
        failures.append(f"homepage returned {status}")
        return
    site_name = content.get("siteName", "")
    if site_name and site_name not in body.decode(errors="replace"):
        failures.append(f"homepage does not mention siteName {site_name!r}")


def check_images(base_url: str, content: dict, failures: list):
    image_paths = []
    for page in content.get("pages") or []:
        for block in page.get("blocks") or []:
            image = str(block.get("image") or "")
            if image:
                image_paths.append(image)
    for image_path in image_paths:
        status, content_type, body = open_request(base_url, image_path)
        if status != 200 or not content_type.startswith("image/") or len(body) < 1024:
            failures.append(f"image {image_path} unusable: status {status}, type {content_type}, {len(body)} bytes")


def check_auth_flow(base_url: str, content: dict, failures: list):
    auth = content.get("auth") or {}
    if not auth.get("enabled"):
        return
    collection = auth.get("userCollection") or "users"
    username = "smoke_" + secrets.token_hex(4)
    password = "smoke-" + secrets.token_hex(8)
    status, _, body = open_request(base_url, f"/api/collections/{collection}/records", "POST",
                                   {"username": username, "password": password, "passwordConfirm": password})
    if status != 200:
        failures.append(f"signup returned {status}: {body[:160].decode(errors='replace')}")
        return
    status, _, body = open_request(base_url, f"/api/collections/{collection}/auth-with-password", "POST",
                                   {"identity": username, "password": password})
    if status != 200:
        failures.append(f"login returned {status}")
        return
    payload = json.loads(body)
    token = payload.get("token", "")
    record_id = (payload.get("record") or {}).get("id", "")
    status, _, _ = open_request(base_url, f"/api/collections/{collection}/auth-refresh", "POST", {}, token)
    if status != 200:
        failures.append(f"session refresh returned {status}")
    if record_id:
        open_request(base_url, f"/api/collections/{collection}/records/{record_id}", "DELETE", None, token)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: site_smoke.py <published site URL>")
        return 2
    site_url = sys.argv[1] if "://" in sys.argv[1] else "https://" + sys.argv[1]
    parsed_url = urllib.parse.urlparse(site_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    failures = []
    content = load_site_content(base_url, failures)
    if content:
        check_homepage(base_url, content, failures)
        check_images(base_url, content, failures)
        check_auth_flow(base_url, content, failures)
    if failures:
        print(f"Site smoke FAILED for {base_url}. Fix these before finishing:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"Site smoke PASSED for {base_url}: homepage, images, and auth flow (when declared) all work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
