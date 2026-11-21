#!/usr/bin/env python3
"""Refresh profile.json and SVG artwork from GitHub's public APIs.

GitHub Actions supplies GITHUB_TOKEN and GITHUB_LOGIN automatically. The
built-in token reads public contributions; an optional user token with
read:user can include private contribution counts when the account exposes
them on its profile.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "profile.json"
AVATAR_PATH = ROOT / "assets" / "avatar.bin"
API_BASE = "https://api.github.com"
MAX_AVATAR_BYTES = 300_000

CONTRIBUTIONS_QUERY = """
query($login: String!, $from: DateTime!, $yearFrom: DateTime!, $to: DateTime!) {
  user(login: $login) {
    orbit: contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
    year: contributionsCollection(from: $yearFrom, to: $to) {
      contributionCalendar { totalContributions }
    }
  }
}
"""


def request_json(url: str, token: str, payload: dict | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "solar-system-profile-readme",
    }
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        details = error.read(500).decode("utf-8", "replace")
        raise RuntimeError(f"GitHub API returned HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach GitHub API: {error.reason}") from error


class GitHubClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def get(self, path: str):
        return request_json(API_BASE + path, self.token)

    def graphql(self, query: str, variables: dict):
        result = request_json(
            API_BASE + "/graphql", self.token,
            {"query": query, "variables": variables},
        )
        if result.get("errors"):
            messages = "; ".join(error.get("message", "Unknown error")
                                 for error in result["errors"])
            raise RuntimeError(f"GitHub GraphQL error: {messages}")
        return result.get("data") or {}

    def avatar(self, url: str) -> tuple[bytes, str]:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "avatars.githubusercontent.com", "github.com",
        }:
            raise RuntimeError("GitHub returned an unexpected avatar URL.")
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["s"] = "128"
        image_url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), "")
        )
        request = Request(
            image_url, headers={"User-Agent": "solar-system-profile-readme"}
        )
        try:
            with urlopen(request, timeout=30) as response:
                mime = response.headers.get_content_type()
                content = response.read(MAX_AVATAR_BYTES + 1)
        except (HTTPError, URLError) as error:
            raise RuntimeError(f"Could not download GitHub avatar: {error}") from error
        if mime not in {"image/png", "image/jpeg", "image/webp"}:
            raise RuntimeError(f"Unsupported avatar image type: {mime}")
        if not content or len(content) > MAX_AVATAR_BYTES:
            raise RuntimeError("GitHub avatar was empty or too large.")
        return content, mime


def owned_repositories(client: GitHubClient, login: str) -> list[dict]:
    repositories = []
    page = 1
    while True:
        path = (
            f"/users/{quote(login, safe='')}/repos?"
            f"per_page=100&page={page}&type=owner&sort=updated"
        )
        batch = client.get(path)
        if not isinstance(batch, list):
            raise RuntimeError("GitHub returned an invalid repository list.")
        repositories.extend(
            repo for repo in batch
            if repo.get("owner", {}).get("login", "").casefold() == login.casefold()
        )
        if len(batch) < 100:
            return repositories
        page += 1


def code_repositories(repositories: list[dict], login: str) -> list[dict]:
    return sorted(
        (
            repo for repo in repositories
            if not repo.get("fork")
            and not repo.get("archived")
            and repo.get("name", "").casefold() != login.casefold()
        ),
        key=lambda repo: (
            repo.get("pushed_at") or repo.get("updated_at") or "",
            repo.get("stargazers_count") or 0,
        ),
        reverse=True,
    )


def repository_languages(
    client: GitHubClient, login: str, repositories: list[dict]
) -> list[dict]:
    totals: Counter[str] = Counter()
    for repo in repositories:
        path = (
            f"/repos/{quote(login, safe='')}/"
            f"{quote(repo['name'], safe='')}/languages"
        )
        languages = client.get(path)
        if not isinstance(languages, dict):
            raise RuntimeError(f"GitHub returned invalid languages for {repo['name']}.")
        for name, byte_count in languages.items():
            totals[name] += max(0, int(byte_count))
    total_bytes = sum(totals.values())
    if not total_bytes:
        return []
    return [
        {"name": name, "percent": round(byte_count * 100 / total_bytes)}
        for name, byte_count in totals.most_common(4)
    ]


def iso_midnight(day: date) -> str:
    return datetime.combine(day, time.min, timezone.utc).isoformat().replace("+00:00", "Z")


def iso_end_of_day(day: date) -> str:
    return datetime.combine(day, time(23, 59, 59), timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def orbit_start(today: date) -> date:
    # GitHub's contribution weeks start on Sunday.
    this_sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    return this_sunday - timedelta(weeks=25)


def orbit_from_calendar(calendar: dict, year_total: int, today: date) -> dict:
    daily: dict[date, int] = {}
    for week in calendar.get("weeks", []):
        for entry in week.get("contributionDays", []):
            day = date.fromisoformat(entry["date"])
            daily[day] = max(0, int(entry["contributionCount"]))

    start = orbit_start(today)
    cells = []
    longest = 0
    running = 0
    for offset in range(26 * 7):
        day = start + timedelta(days=offset)
        if day > today:
            break
        count = daily.get(day, 0)
        if count:
            cells.append({"week": offset // 7, "day": offset % 7, "count": count})
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    # A quiet current day does not end the streak until the day is over.
    cursor = today if daily.get(today, 0) else today - timedelta(days=1)
    current = 0
    while cursor >= start and daily.get(cursor, 0):
        current += 1
        cursor -= timedelta(days=1)
    return {
        "days": current,
        "longest_days": longest,
        "revolutions_this_year": max(0, int(year_total)),
        "cells": cells,
    }


def contributions(client: GitHubClient, login: str, today: date) -> dict:
    start = orbit_start(today)
    variables = {
        "login": login,
        "from": iso_midnight(start),
        "yearFrom": iso_midnight(date(today.year, 1, 1)),
        "to": iso_end_of_day(today),
    }
    data = client.graphql(CONTRIBUTIONS_QUERY, variables)
    user = data.get("user")
    if not user:
        raise RuntimeError(f"GitHub GraphQL could not find user {login}.")
    orbit_calendar = user["orbit"]["contributionCalendar"]
    year_total = user["year"]["contributionCalendar"]["totalContributions"]
    return orbit_from_calendar(orbit_calendar, year_total, today)


def recent_pushes(client: GitHubClient, login: str) -> list[dict]:
    events = client.get(f"/users/{quote(login, safe='')}/events/public?per_page=100")
    if not isinstance(events, list):
        raise RuntimeError("GitHub returned an invalid public event list.")
    pushes = []
    for event in events:
        if event.get("type") != "PushEvent":
            continue
        name = event.get("repo", {}).get("name", "").split("/")[-1]
        when = event.get("created_at", "")[:10]
        if name and when:
            pushes.append({"repo": name, "date": when})
        if len(pushes) == 5:
            break
    return pushes


def build_profile(client: GitHubClient, login: str, today: date) -> tuple[dict, str | None]:
    user = client.get(f"/users/{quote(login, safe='')}")
    if not isinstance(user, dict) or user.get("type") != "User":
        raise RuntimeError(f"GitHub account {login} was not found as a user.")
    username = user["login"]
    repositories = owned_repositories(client, username)
    eligible = code_repositories(repositories, username)
    moons = [
        {
            "name": repo["name"],
            "description": repo.get("description") or "A project in progress.",
            "stars": int(repo.get("stargazers_count") or 0),
            "forks": int(repo.get("forks_count") or 0),
            "language": repo.get("language"),
        }
        for repo in eligible[:4]
    ]
    bio = user.get("bio") or (
        f"Working on {moons[0]['name']} right now." if moons else "Building on GitHub."
    )
    profile = {
        "username": username,
        "refreshed_on": today.isoformat(),
        "bio": bio,
        "followers": int(user.get("followers") or 0),
        "repositories": int(user.get("public_repos") or 0),
        "stars": sum(int(repo.get("stargazers_count") or 0) for repo in repositories),
        "moons": moons,
        "languages": repository_languages(client, username, eligible),
        "orbit": contributions(client, username, today),
        "recent_pushes": recent_pushes(client, username),
    }
    return profile, user.get("avatar_url")


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("Set GITHUB_TOKEN to refresh the GitHub profile.")
    existing = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    login = os.environ.get("GITHUB_LOGIN") or existing["username"]
    client = GitHubClient(token)
    today = datetime.now(timezone.utc).date()
    profile, avatar_url = build_profile(client, login, today)

    avatar_bytes = None
    if avatar_url:
        avatar_bytes, profile["avatar_mime"] = client.avatar(avatar_url)
    else:
        profile["avatar_mime"] = None

    AVATAR_PATH.parent.mkdir(exist_ok=True)
    if avatar_bytes is None:
        AVATAR_PATH.unlink(missing_ok=True)
    elif not AVATAR_PATH.exists() or AVATAR_PATH.read_bytes() != avatar_bytes:
        AVATAR_PATH.write_bytes(avatar_bytes)

    temp_path = PROFILE_PATH.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(PROFILE_PATH)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate.py")], check=True)
    print(f"Refreshed @{profile['username']} from GitHub.")


if __name__ == "__main__":
    main()
