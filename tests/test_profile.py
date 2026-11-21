import base64
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import generate  # noqa: E402
import sync_github  # noqa: E402


TODAY = date(2026, 11, 21)


class FakeGitHub:
    def __init__(self):
        owner = {"login": "devjysh"}
        self.repositories = [
            {
                "owner": owner, "name": "devjysh", "fork": False, "archived": False,
                "pushed_at": "2026-11-21T12:00:00Z", "stargazers_count": 0,
                "forks_count": 0, "language": "Python",
            },
            {
                "owner": owner, "name": "Rivet", "fork": False, "archived": False,
                "pushed_at": "2026-11-20T12:00:00Z", "stargazers_count": 5,
                "forks_count": 1, "language": "Python", "description": "Main project",
            },
            {
                "owner": owner, "name": "Nebula", "fork": False, "archived": False,
                "pushed_at": "2026-11-21T09:00:00Z", "stargazers_count": 2,
                "forks_count": 0, "language": "C", "description": "Space tools",
            },
            {
                "owner": owner, "name": "OldFork", "fork": True, "archived": False,
                "pushed_at": "2026-11-19T09:00:00Z", "stargazers_count": 7,
                "forks_count": 0, "language": "Shell",
            },
        ]

    def get(self, path):
        if path == "/users/devjysh":
            return {
                "type": "User", "login": "devjysh", "bio": "Building space tools.",
                "followers": 12, "public_repos": 4,
                "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
            }
        if path.startswith("/users/devjysh/repos?"):
            return self.repositories
        if path.endswith("/Rivet/languages"):
            return {"Python": 500, "Shell": 300}
        if path.endswith("/Nebula/languages"):
            return {"Python": 100, "C": 100}
        if path.endswith("/events/public?per_page=100"):
            return [
                {"type": "IssuesEvent", "repo": {"name": "devjysh/Rivet"}},
                {"type": "PushEvent", "repo": {"name": "devjysh/Nebula"},
                 "created_at": "2026-11-21T09:00:00Z"},
            ]
        raise AssertionError(f"Unexpected API request: {path}")

    def graphql(self, query, variables):
        self.variables = variables
        days = [
            ("2026-11-10", 1), ("2026-11-11", 1), ("2026-11-12", 1),
            ("2026-11-20", 1), ("2026-11-21", 2),
        ]
        return {
            "user": {
                "orbit": {"contributionCalendar": {
                    "weeks": [{"contributionDays": [
                        {"date": day, "contributionCount": count}
                        for day, count in days
                    ]}]
                }},
                "year": {"contributionCalendar": {"totalContributions": 19}},
            }
        }

    def avatar(self, url):
        tiny_png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
            "AAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg=="
        )
        return base64.b64decode(tiny_png), "image/png"


class ProfileTests(unittest.TestCase):
    def test_sync_uses_live_profile_repositories_languages_and_calendar(self):
        api = FakeGitHub()
        profile, avatar_url = sync_github.build_profile(api, "devjysh", TODAY)

        self.assertEqual(profile["bio"], "Building space tools.")
        self.assertEqual(profile["refreshed_on"], "2026-11-21")
        self.assertEqual(profile["followers"], 12)
        self.assertEqual(profile["repositories"], 4)
        self.assertEqual(profile["stars"], 14)
        self.assertEqual([repo["name"] for repo in profile["moons"]],
                         ["Nebula", "Rivet"])
        self.assertEqual(profile["languages"], [
            {"name": "Python", "percent": 60},
            {"name": "Shell", "percent": 30},
            {"name": "C", "percent": 10},
        ])
        self.assertEqual(profile["orbit"]["days"], 2)
        self.assertEqual(profile["orbit"]["longest_days"], 3)
        self.assertEqual(profile["orbit"]["revolutions_this_year"], 19)
        self.assertEqual(len(profile["orbit"]["cells"]), 5)
        self.assertEqual(profile["recent_pushes"],
                         [{"repo": "Nebula", "date": "2026-11-21"}])
        self.assertEqual(avatar_url, "https://avatars.githubusercontent.com/u/123?v=4")
        self.assertTrue(api.variables["from"].startswith("2026-05-24"))
        self.assertTrue(api.variables["yearFrom"].startswith("2026-01-01"))

    def test_quiet_today_keeps_yesterdays_streak(self):
        calendar = {"weeks": [{"contributionDays": [
            {"date": "2026-11-19", "contributionCount": 1},
            {"date": "2026-11-20", "contributionCount": 1},
        ]}]}
        orbit = sync_github.orbit_from_calendar(calendar, 9, TODAY)
        self.assertEqual(orbit["days"], 2)
        self.assertEqual(orbit["longest_days"], 2)

    def test_artwork_expands_for_more_moons_and_links_to_them(self):
        original = generate.PROFILE
        try:
            profile = copy.deepcopy(original)
            profile["moons"] = [
                {"name": name, "description": "A new project", "stars": 1,
                 "forks": 0, "language": "Rust"}
                for name in ("One", "Two", "Three")
            ]
            profile["recent_pushes"] = [{"repo": "One", "date": "2026-11-21"}]
            generate.PROFILE = profile
            desktop = generate.desktop()
            mobile = generate.mobile()
            readme = generate.readme()
            self.assertEqual(ElementTree.fromstring(desktop).attrib["viewBox"],
                             "0 0 814 1655")
            self.assertEqual(ElementTree.fromstring(mobile).attrib["viewBox"],
                             "0 0 390 1712")
            self.assertIn("MOON 03", desktop)
            self.assertIn("Push to One", desktop)
            self.assertIn("https://github.com/devjysh/Three", readme)
        finally:
            generate.PROFILE = original

    def test_full_refresh_writes_live_readme_and_embeds_avatar(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory)
            (temp_root / "scripts").mkdir()
            shutil.copy(ROOT / "scripts" / "generate.py",
                        temp_root / "scripts" / "generate.py")
            shutil.copy(ROOT / "profile.json", temp_root / "profile.json")
            with (
                patch.object(sync_github, "ROOT", temp_root),
                patch.object(sync_github, "PROFILE_PATH", temp_root / "profile.json"),
                patch.object(sync_github, "AVATAR_PATH", temp_root / "assets" / "avatar.bin"),
                patch.object(sync_github, "GitHubClient", return_value=FakeGitHub()),
                patch.dict(os.environ, {"GITHUB_TOKEN": "test-token", "GITHUB_LOGIN": "devjysh"}),
            ):
                sync_github.main()

            refreshed = json.loads((temp_root / "profile.json").read_text())
            artwork = (temp_root / "assets" / "solar-system.svg").read_text()
            readme = (temp_root / "README.md").read_text()
            self.assertEqual(refreshed["bio"], "Building space tools.")
            self.assertIn("Building space tools.", artwork)
            self.assertIn("data:image/png;base64,", artwork)
            self.assertIn("https://github.com/devjysh/Nebula", readme)
            self.assertNotIn("Working on Rivet right now.", readme)
            ElementTree.fromstring(artwork)


if __name__ == "__main__":
    unittest.main()
