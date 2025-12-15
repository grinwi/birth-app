import base64
import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional, Tuple

# Environment configuration with sensible defaults
GITHUB_OWNER = os.getenv("GITHUB_REPO_OWNER", "grinwi")
GITHUB_REPO = os.getenv("GITHUB_REPO", "birth-app")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GITHUB_FILE_PATH = os.getenv("GITHUB_FILE_PATH", "birthdays.csv")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("BIRTHDAY_APP_EDIT_CSV_TOKEN")

GITHUB_API_BASE = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"


def _headers_json() -> dict:
    if not GITHUB_TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN or BIRTHDAY_APP_EDIT_CSV_TOKEN")
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "birthdays-app-python",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_request(url: str, method: str = "GET", data: Optional[dict] = None, headers: Optional[dict] = None):
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error calling {url}: {e}")


def get_base_sha(owner: str, repo: str, branch: str) -> str:
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/ref/heads/{branch}"
    status, resp = github_request(url, headers=_headers_json())
    if status != 200:
        raise RuntimeError(f"Failed to resolve base ref: {status} {resp.decode('utf-8', 'ignore')}")
    data = json.loads(resp.decode("utf-8"))
    sha = (data.get("object") or {}).get("sha")
    if not sha:
        raise RuntimeError("Base branch SHA not found")
    return sha


def create_branch(owner: str, repo: str, base_sha: str, preferred_name: Optional[str] = None) -> str:
    # Try to create a unique branch name
    base = preferred_name or f"update-birthdays-{time.strftime('%Y%m%d%H%M%S')}"
    for i in range(6):
        name = base if i == 0 else f"{base}-{i}"
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs"
        status, resp = github_request(
            url,
            method="POST",
            data={"ref": f"refs/heads/{name}", "sha": base_sha},
            headers=_headers_json(),
        )
        if status == 201:
            return name
        # 422 means already exists, try next suffix
        if status != 422:
            raise RuntimeError(f"Failed to create branch: {status} {resp.decode('utf-8', 'ignore')}")
    raise RuntimeError("Could not create unique PR branch after multiple attempts")


def get_file_sha(owner: str, repo: str, path: str, ref: str) -> Optional[str]:
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{urllib.parse.quote(path)}?ref={urllib.parse.quote(ref)}"
    status, resp = github_request(url, headers=_headers_json())
    if status == 200:
        data = json.loads(resp.decode("utf-8"))
        return data.get("sha")
    if status == 404:
        return None
    raise RuntimeError(f"Failed to fetch file metadata: {status} {resp.decode('utf-8', 'ignore')}")


def put_file(owner: str, repo: str, path: str, branch: str, content_utf8: str, message: str, sha: Optional[str]) -> None:
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{urllib.parse.quote(path)}"
    payload = {
        "message": message,
        "content": base64.b64encode(content_utf8.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    status, resp = github_request(url, method="PUT", data=payload, headers=_headers_json())
    if status not in (200, 201):
        raise RuntimeError(f"Failed to update file on GitHub: {status} {resp.decode('utf-8', 'ignore')}")


def open_pr(owner: str, repo: str, head: str, base: str, title: str, body: str) -> Tuple[int, str]:
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
    status, resp = github_request(
        url,
        method="POST",
        data={"title": title, "head": head, "base": base, "body": body},
        headers=_headers_json(),
    )
    if status not in (200, 201):
        raise RuntimeError(f"Failed to open PR: {status} {resp.decode('utf-8', 'ignore')}")
    data = json.loads(resp.decode("utf-8"))
    return data.get("number"), data.get("html_url")


def fetch_raw_csv(owner: str, repo: str, branch: str, path: str) -> str:
    url = f"{RAW_BASE}/{owner}/{repo}/{branch}/{path}"
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "birthdays-app-python"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Treat missing as empty CSV with header
            return ""
        raise
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error fetching raw CSV: {e}")


def create_pr_with_csv(new_csv_text: str, title: str, body: str = "") -> Tuple[int, str]:
    owner = GITHUB_OWNER
    repo = GITHUB_REPO
    base = GITHUB_BRANCH
    path = GITHUB_FILE_PATH

    base_sha = get_base_sha(owner, repo, base)
    branch_name = create_branch(owner, repo, base_sha, preferred_name=f"update-birthdays-{time.strftime('%Y%m%d%H%M%S')}")
    file_sha = get_file_sha(owner, repo, path, branch_name)
    put_file(owner, repo, path, branch_name, new_csv_text, message=title, sha=file_sha)
    pr_number, pr_url = open_pr(owner, repo, branch_name, base, title=title, body=body or "Automated update of birthdays.csv")
    return pr_number, pr_url
