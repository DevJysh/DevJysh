#!/usr/bin/env python3
"""Build the self-contained SVG artwork and GitHub profile README.

The GitHub workflow updates profile.json from public API data before this
generator runs. The artwork uses SVG shapes and system fonts, so GitHub can
render it without a third-party image service.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import random
import textwrap
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PROFILE = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))

INK = "#e6ebf5"
MUTED = "#bdc5d4"
DIM = "#8d9bb5"
GOLD = "#f5ce59"
MONO = "SFMono-Regular,Consolas,Liberation Mono,monospace"
SANS = "Inter,Segoe UI,Arial,sans-serif"
LANG_COLORS = {
    "Python": "#4184b6",
    "Shell": "#79dc4c",
    "C": "#686a70",
    "Makefile": "#467e1c",
    "JavaScript": "#f1c54b",
    "TypeScript": "#468aca",
    "Rust": "#c76c4f",
    "Go": "#62b5c5",
    "HTML": "#e97b4e",
    "CSS": "#8a6bd2",
    "Java": "#d47957",
}
EXTRA_COLORS = ("#a780d8", "#d57e9a", "#56b6ab", "#d39b5a")


def language_color(name: str) -> str:
    if name in LANG_COLORS:
        return LANG_COLORS[name]
    index = hashlib.sha256(name.encode("utf-8")).digest()[0] % len(EXTRA_COLORS)
    return EXTRA_COLORS[index]


def compact(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}m"
    if value >= 10_000:
        return f"{value / 1_000:.0f}k"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def shortened(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def wrapped(value: str, width: int, max_lines: int = 2) -> list[str]:
    lines = textwrap.wrap(value, width=width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


def moons() -> list[dict]:
    if "moons" in PROFILE:
        return PROFILE["moons"][:4]
    featured = PROFILE.get("featured_repository")
    return [featured] if featured and featured.get("name") else []


def avatar_data_uri() -> str | None:
    mime = PROFILE.get("avatar_mime")
    avatar_path = ASSETS / "avatar.bin"
    if mime not in {"image/png", "image/jpeg", "image/webp"} or not avatar_path.is_file():
        return None
    payload = base64.b64encode(avatar_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


AVATAR_DATA_URI = avatar_data_uri()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def n(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def text(
    x: float,
    y: float,
    value: object,
    size: float,
    *,
    fill: str = INK,
    family: str = SANS,
    weight: int = 400,
    anchor: str = "start",
    spacing: float = 0,
    opacity: float = 1,
) -> str:
    return (
        f'<text x="{n(x)}" y="{n(y)}" fill="{fill}" '
        f'font-family="{family}" font-size="{n(size)}" font-weight="{weight}" '
        f'text-anchor="{anchor}" letter-spacing="{n(spacing)}" '
        f'opacity="{n(opacity)}">{esc(value)}</text>'
    )


def stars(x: float, y: float, w: float, h: float, seed: int, count: int) -> str:
    rng = random.Random(seed)
    dots = []
    for _ in range(count):
        cx = x + rng.uniform(1, w - 1)
        cy = y + rng.uniform(1, h - 1)
        radius = rng.choices([0.45, 0.65, 0.85, 1.15], [4, 5, 3, 1])[0]
        opacity = rng.uniform(0.18, 0.7)
        dots.append(
            f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(radius)}" '
            f'fill="#e4edff" opacity="{n(opacity)}"/>'
        )
    return "".join(dots)


def card(x: float, y: float, w: float, h: float, key: str, seed: int, count: int) -> str:
    gradient = "hero" if key == "hero" else "card"
    return (
        f'<defs><clipPath id="clip-{key}"><rect x="{n(x)}" y="{n(y)}" '
        f'width="{n(w)}" height="{n(h)}" rx="15"/></clipPath></defs>'
        f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" '
        f'rx="15" fill="url(#{gradient})"/>'
        f'<g clip-path="url(#clip-{key})">{stars(x, y, w, h, seed, count)}</g>'
    )


def avatar(cx: float, cy: float, radius: float) -> str:
    scale = radius / 50
    pixels = [
        (-25, -24), (9, -24),
        (-42, 10), (-8, 10), (26, 10),
        (-25, 27), (9, 27),
    ]
    blocks = "".join(
        f'<rect x="{px}" y="{py}" width="16" height="17" fill="#a077d8"/>'
        for px, py in pixels
    )
    live_avatar = (
        '<image x="-48" y="-48" width="96" height="96" '
        'preserveAspectRatio="xMidYMid slice" '
        'clip-path="url(#avatarClip)" '
        f'href="{AVATAR_DATA_URI}"/>'
        if AVATAR_DATA_URI else ""
    )
    return (
        f'<g transform="translate({n(cx)} {n(cy)}) scale({n(scale)})">'
        '<circle r="50" fill="#f6f2e9"/>'
        '<circle r="48" fill="#fbf8ef" opacity=".58"/>'
        f"{blocks}"
        f"{live_avatar}"
        '<circle r="50" fill="none" stroke="#f4c84e" stroke-width="3"/>'
        "</g>"
    )


def planet(kind: str, cx: float, cy: float, radius: float) -> str:
    scale = radius / 18
    if kind == "Python":
        inside = (
            '<circle r="18" fill="url(#pythonBlue)"/>'
            '<path d="M-8-6q0-6 6-6h7q5 0 5 5v6H0q-4 0-4 4v1h-7V0q0-4 3-6Z" '
            'fill="#f7fbff"/>'
            '<path d="M8 6q0 6-6 6h-7q-5 0-5-5V1H0q4 0 4-4v-1h7v4q0 4-3 6Z" '
            'fill="#d9edfb"/>'
            '<circle cx="2.5" cy="-8.5" r="1.2" fill="#397aa9"/>'
            '<circle cx="-2.5" cy="8.5" r="1.2" fill="#397aa9"/>'
        )
    elif kind == "Shell":
        inside = (
            '<circle r="18" fill="#8be452"/>'
            '<path d="M0-9 8-5v10L0 9-8 5V-5Z" fill="none" '
            'stroke="#317c24" stroke-width="1.7" stroke-linejoin="round"/>'
            '<path d="M-8-5 0-1 8-5M0-1v10" fill="none" '
            'stroke="#317c24" stroke-width="1.4"/>'
        )
    elif kind == "C":
        inside = (
            '<circle r="18" fill="url(#cGray)"/>'
            f'{text(0, 8, "C", 25, fill="#fff", weight=800, anchor="middle")}'
        )
    elif kind == "Makefile":
        inside = (
            '<circle r="18" fill="#3d791e"/>'
            '<circle r="13.5" fill="none" stroke="#75b63d" stroke-width=".8" opacity=".6"/>'
            f'{text(0, 5, "M", 13, fill="#c5e5b5", family=MONO, weight=700, anchor="middle")}'
        )
    else:
        initials = "".join(word[0] for word in kind.split()[:2]).upper() or "?"
        inside = (
            f'<circle r="18" fill="{language_color(kind)}"/>'
            f'{text(0, 5, initials, 12 if len(initials) > 1 else 16, fill="#fff", family=MONO, weight=700, anchor="middle")}'
        )
    return (
        f'<g transform="translate({n(cx)} {n(cy)}) scale({n(scale)})">'
        f"{inside}</g>"
    )


def saturn(cx: float, cy: float) -> str:
    return (
        f'<g transform="translate({n(cx)} {n(cy)})">'
        '<ellipse rx="13" ry="4.2" transform="rotate(-15)" fill="none" '
        'stroke="#7e9dbd" stroke-width="1" opacity=".75"/>'
        '<circle r="7.5" fill="#2c628b"/>'
        '<path d="M-6-2q6 2 12 0M-6 3q6 2 12 0" fill="none" '
        'stroke="#4d83ae" stroke-width="1" opacity=".8"/>'
        '<path d="M-13 2q13 4 26-4" fill="none" stroke="#a0b5cf" '
        'stroke-width=".8" opacity=".85"/>'
        "</g>"
    )


def orbit_grid(x: float, y: float, size: float, gap: float) -> str:
    active = {
        (cell["week"], cell["day"]): cell["count"]
        for cell in PROFILE["orbit"].get("cells", [])
    }
    heat = ("#1e2638", "#3e5d9f", "#6987e4", "#9d83d9", "#f3c85e")
    cells = []
    for row in range(7):
        for col in range(26):
            count = active.get((col, row), 0)
            fill = heat[min(count, len(heat) - 1)] if count >= 0 else heat[0]
            cells.append(
                f'<rect x="{n(x + col * (size + gap))}" '
                f'y="{n(y + row * (size + gap))}" '
                f'width="{n(size)}" height="{n(size)}" rx="2" fill="{fill}"/>'
            )
    return "".join(cells)


def bar_row(
    y: float, name: str, percent: float, label_x: float, bar_x: float,
    bar_w: float, percent_x: float, icon_radius: float, text_size: float,
) -> str:
    color = language_color(name)
    max_percent = max((item["percent"] for item in PROFILE["languages"]), default=0)
    fill_w = max(0, bar_w * percent / max_percent) if max_percent else 0
    label_limit = 13 if bar_w <= 160 else 18
    return (
        planet(name, label_x + icon_radius, y, icon_radius)
        + text(label_x + icon_radius * 2 + 8, y + 4,
               shortened(name, label_limit), text_size, weight=600)
        + f'<rect x="{n(bar_x)}" y="{n(y - 6.5)}" width="{n(bar_w)}" '
        f'height="13" rx="6.5" fill="#292d3b"/>'
        + f'<rect x="{n(bar_x)}" y="{n(y - 6.5)}" width="{n(fill_w)}" '
        f'height="13" rx="6.5" fill="{color}"/>'
        + text(percent_x, y + 3.5, f"{percent}%", 10.5, fill="#abb9da",
               family=MONO, anchor="end")
    )


def stats_line() -> str:
    followers = PROFILE["followers"]
    repos = PROFILE["repositories"]
    stars_count = PROFILE["stars"]
    repo_word = "repository" if repos == 1 else "repositories"
    return (
        f"{compact(followers)} followers · {compact(repos)} {repo_word}"
        f" · ★ {compact(stars_count)} stars"
    )


def comets(mobile: bool = False) -> str:
    recent = PROFILE.get("recent_pushes", [])[:5]
    positions = (
        [(316, 102), (77, 269), (304, 270), (339, 225), (53, 125)]
        if mobile else
        [(604, 145), (271, 335), (562, 337), (698, 296), (151, 184)]
    )
    streaks = []
    for event, (x, y) in zip(recent, positions):
        title = f'Push to {event["repo"]} on {event["date"]}'
        streaks.append(
            '<g>'
            f'<title>{esc(title)}</title>'
            f'<path d="M{n(x - 21)} {n(y + 8)} Q{n(x - 8)} {n(y + 3)} '
            f'{n(x)} {n(y)}" fill="none" stroke="#a2b7ed" '
            'stroke-width="1.2" opacity=".55"/>'
            f'<circle cx="{x}" cy="{y}" r="2" fill="#f6d76e"/>'
            "</g>"
        )
    return "".join(streaks)


def hero_planets(mobile: bool = False) -> str:
    slots = (
        [(50, 200, 10, 224), (155, 110, 13, 136),
         (130, 151, 14, 176), (258, 149, 15, 177)]
        if mobile else
        [(186, 257, 11, 283), (387, 165, 16, 194),
         (344, 191, 16, 220), (471, 212, 18, 244)]
    )
    positions = {1: [3], 2: [0, 3], 3: [0, 2, 3], 4: [0, 1, 2, 3]}
    languages = PROFILE["languages"][:4]
    if not languages:
        return ""
    parts = []
    for item, index in zip(reversed(languages), positions[len(languages)]):
        x, y, radius, label_y = slots[index]
        parts.append(planet(item["name"], x, y, radius))
        parts.append(text(
            x, label_y, f'{shortened(item["name"], 10)} {item["percent"]}%',
            8.5 if mobile else 9.4, fill="#d8d8de",
            family=MONO, anchor="middle",
        ))
    return "".join(parts)


def moon_card(repo: dict | None, index: int, x: int, y: int, mobile: bool) -> str:
    width, height = (354, 160) if mobile else (344, 163)
    label_x = x + (19 if mobile else 24)
    label_y = y + (32 if mobile else 36)
    title_y = y + (62 if mobile else 65)
    description_y = y + (89 if mobile else 91)
    metrics_y = y + (135 if mobile else 137)
    parts = [card(x, y, width, height, f"moon-{index}", 27 + index, 26)]
    parts.append(text(label_x, label_y, f"MOON {index:02d}", 9.3,
                      fill=GOLD, family=MONO, weight=700, spacing=1.8))
    parts.append(saturn(x + (319 if mobile else 295), y + (34 if mobile else 39)))
    if repo is None:
        parts.append(text(label_x, title_y, "No public projects yet",
                          18 if mobile else 16, weight=750))
        parts.append(text(label_x, description_y, "Your next project will appear here.",
                          12.2, fill=MUTED))
        return "".join(parts)

    parts.append(text(label_x, title_y, shortened(repo["name"], 28),
                      18 if mobile else 16, weight=750))
    description = repo.get("description") or "A project in progress."
    for line_index, line in enumerate(wrapped(description, width=44)):
        parts.append(text(label_x, description_y + line_index * 15,
                          line, 12.2 if not mobile else 12.5, fill=MUTED))
    parts.append(text(
        label_x, metrics_y,
        f'★ {compact(int(repo.get("stars", 0)))}   ⑂ {compact(int(repo.get("forks", 0)))}',
        10.8, fill="#afbbd4", family=MONO,
    ))
    language = repo.get("language")
    if language:
        icon_x = x + (159 if mobile else 155)
        parts.append(planet(language, icon_x, metrics_y - 4, 8))
        parts.append(text(icon_x + 13, metrics_y, shortened(language, 18),
                          10.8, fill="#afbbd4"))
    return "".join(parts)


DEFS = """
<defs>
  <linearGradient id="page" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#101719"/>
    <stop offset=".75" stop-color="#0d1315"/>
    <stop offset="1" stop-color="#0a100e"/>
  </linearGradient>
  <linearGradient id="hero" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#070a14"/>
    <stop offset="1" stop-color="#040711"/>
  </linearGradient>
  <linearGradient id="card" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0c1230"/>
    <stop offset="1" stop-color="#050914"/>
  </linearGradient>
  <linearGradient id="pythonBlue" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#75add0"/>
    <stop offset="1" stop-color="#285d86"/>
  </linearGradient>
  <linearGradient id="cGray" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#898b8d"/>
    <stop offset="1" stop-color="#4b4c50"/>
  </linearGradient>
  <radialGradient id="sunGlow">
    <stop offset="0" stop-color="#f9c955" stop-opacity=".43"/>
    <stop offset=".4" stop-color="#d9a33b" stop-opacity=".19"/>
    <stop offset="1" stop-color="#d9a33b" stop-opacity="0"/>
  </radialGradient>
  <clipPath id="avatarClip"><circle r="48"/></clipPath>
</defs>
"""


def document(width: int, height: int, body: str) -> str:
    featured = moons()
    featured_text = (
        f"Featured project {featured[0]['name']}." if featured else "No public projects yet."
    )
    description = (
        f"Solar System profile for {PROFILE['username']}: "
        f"{PROFILE['bio']} {featured_text}"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        'role="img" aria-labelledby="title desc">'
        f'<title id="title">Solar System · @{esc(PROFILE["username"])}</title>'
        f'<desc id="desc">{esc(description)}</desc>'
        f"{DEFS}{body}</svg>\n"
    )


def desktop() -> str:
    visible_moons = moons()
    moon_rows = max(1, (len(visible_moons) + 1) // 2)
    shift = (moon_rows - 1) * 179
    planets_y = 894 + shift
    orbit_y = 1111 + shift
    height = 1476 + shift
    p: list[str] = [f'<rect width="814" height="{height}" fill="url(#page)"/>']
    p.append(card(59, 40, 702, 414, "hero", 91, 112))
    p.append(text(78, 67, f'SOLAR SYSTEM · @{PROFILE["username"].upper()}',
                  9, fill="#c7cfdb", family=MONO, spacing=1.3))
    for rx, ry in [(228, 127), (188, 106), (148, 83), (109, 60)]:
        p.append(
            f'<ellipse cx="410" cy="254" rx="{rx}" ry="{ry}" fill="none" '
            'stroke="#5b657a" stroke-width=".75" stroke-dasharray="1.1 5.8" '
            'opacity=".37"/>'
        )
    p.append('<circle cx="410" cy="254" r="112" fill="url(#sunGlow)"/>')
    p.append(comets())
    p.append(hero_planets())
    p.append(avatar(410, 254, 29))
    p.append(text(78, 441, "gitskins.com", 9, fill="#aeb3c2", family=MONO))
    p.append(text(743, 441,
                  "planets = languages · moons = repos · comets = recent pushes",
                  9, fill="#aeb3c2", family=MONO, anchor="end"))

    p.append(text(59, 489,
                  "I am the sun; my languages are the planets and my projects their moons.",
                  11.5, fill="#b9c2ca"))

    p.append(card(59, 508, 702, 183, "sun", 14, 38))
    p.append(text(88, 547, "THE SUN", 9.5, fill=GOLD, family=MONO,
                  weight=700, spacing=2))
    p.append(text(88, 578, shortened(PROFILE["username"], 28),
                  26 if len(PROFILE["username"]) <= 20 else 21, weight=800))
    bio_lines = wrapped(PROFILE["bio"] or "No bio yet.", width=68)
    for index, line in enumerate(bio_lines):
        p.append(text(88, 614 + index * 18, line, 15, fill=MUTED))
    p.append(text(88, 660, stats_line(), 10.8, fill=DIM, family=MONO))
    p.append(avatar(682, 606, 51))

    for index, repo in enumerate(visible_moons or [None], start=1):
        x = 59 if index % 2 else 417
        y = 707 + ((index - 1) // 2) * 179
        p.append(moon_card(repo, index, x, y, False))

    p.append(card(59, planets_y, 702, 201, "planets", 38, 33))
    p.append(text(88, planets_y + 40, "PLANETS", 9.5, fill=GOLD, family=MONO,
                  weight=700, spacing=2))
    for y, item in zip((planets_y + 83, planets_y + 112,
                        planets_y + 141, planets_y + 170), PROFILE["languages"][:4]):
        p.append(bar_row(y, item["name"], item["percent"], 88, 242, 432,
                         733, 9, 12.4))
    if not PROFILE["languages"]:
        p.append(text(88, planets_y + 102, "No public language data yet.",
                      13, fill=MUTED))

    p.append(card(59, orbit_y, 702, 211, "orbit", 49, 35))
    p.append(text(88, orbit_y + 42, "ORBIT LOG · 26 WEEKS", 9.5, fill=GOLD,
                  family=MONO, weight=700, spacing=1.7))
    p.append(orbit_grid(88, orbit_y + 69, 10, 3))
    orbit = PROFILE["orbit"]
    for label, value, y in [
        ("DAYS IN ORBIT", f'{orbit["days"]} days', orbit_y + 74),
        ("LONGEST ORBIT", f'{orbit["longest_days"]} days', orbit_y + 116),
        ("REVOLUTIONS THIS YEAR", orbit["revolutions_this_year"], orbit_y + 158),
    ]:
        p.append(text(474, y, label, 9.3, fill="#aab6ce",
                      family=MONO, spacing=.65))
        p.append(text(474, y + 21, value, 19, weight=750))

    p.append(text(59, orbit_y + 242, "GitHub", 14.5, fill="#5fb6f8"))
    p.append(text(59, orbit_y + 283,
                  "Solar System · planets are languages, comets are recent pushes · inspired by GitSkins",
                  10.5, fill="#bfc7ca"))
    if PROFILE.get("refreshed_on"):
        p.append(text(743, orbit_y + 283, f'updated {PROFILE["refreshed_on"]}',
                      9, fill=DIM, family=MONO, anchor="end"))
    return document(814, height, "".join(p))


def mobile() -> str:
    visible_moons = moons()
    moon_count = max(1, len(visible_moons))
    shift = (moon_count - 1) * 176
    planets_y = 772 + shift
    orbit_y = 998 + shift
    height = 1360 + shift
    p: list[str] = [f'<rect width="390" height="{height}" fill="url(#page)"/>']
    p.append(card(18, 18, 354, 340, "hero", 91, 78))
    p.append(text(34, 47, f'SOLAR SYSTEM · @{PROFILE["username"].upper()}',
                  9.5, fill="#c7cfdb", family=MONO, spacing=.8))
    for rx, ry in [(156, 91), (127, 74), (97, 57), (67, 39)]:
        p.append(
            f'<ellipse cx="195" cy="184" rx="{rx}" ry="{ry}" fill="none" '
            'stroke="#5b657a" stroke-width=".75" stroke-dasharray="1 5" '
            'opacity=".4"/>'
        )
    p.append('<circle cx="195" cy="184" r="85" fill="url(#sunGlow)"/>')
    p.append(comets(mobile=True))
    p.append(hero_planets(mobile=True))
    p.append(avatar(195, 184, 27))
    p.append(text(34, 337, "gitskins.com", 8.5, fill="#aeb3c2", family=MONO))
    p.append(text(356, 337, "planets = languages", 8.5,
                  fill="#aeb3c2", family=MONO, anchor="end"))

    p.append(text(18, 387, "I am the sun; my languages are the planets", 12,
                  fill="#b9c2ca"))
    p.append(text(18, 405, "and my projects their moons.", 12, fill="#b9c2ca"))

    p.append(card(18, 425, 354, 155, "sun", 14, 28))
    p.append(text(37, 455, "THE SUN", 9.3, fill=GOLD, family=MONO,
                  weight=700, spacing=1.8))
    p.append(text(37, 485, shortened(PROFILE["username"], 24),
                  24 if len(PROFILE["username"]) <= 15 else 18, weight=800))
    lines = wrapped(PROFILE["bio"] or "No bio yet.", width=43)
    for index, line in enumerate(lines):
        p.append(text(37, 512 + index * 17, line, 12.6, fill=MUTED))
    p.append(text(37, 560, stats_line(), 8.9, fill=DIM, family=MONO))
    p.append(avatar(325, 473, 34))

    for index, repo in enumerate(visible_moons or [None], start=1):
        p.append(moon_card(repo, index, 18, 596 + (index - 1) * 176, True))

    p.append(card(18, planets_y, 354, 210, "planets", 38, 27))
    p.append(text(37, planets_y + 33, "PLANETS", 9.3, fill=GOLD, family=MONO,
                  weight=700, spacing=1.8))
    for y, item in zip((planets_y + 67, planets_y + 104,
                        planets_y + 141, planets_y + 178), PROFILE["languages"][:4]):
        p.append(bar_row(y, item["name"], item["percent"], 37, 157, 157,
                         354, 8.5, 11.5))
    if not PROFILE["languages"]:
        p.append(text(37, planets_y + 75, "No public language data yet.",
                      12.5, fill=MUTED))

    p.append(card(18, orbit_y, 354, 245, "orbit", 49, 29))
    p.append(text(37, orbit_y + 33, "ORBIT LOG · 26 WEEKS", 9.3, fill=GOLD,
                  family=MONO, weight=700, spacing=1.5))
    p.append(orbit_grid(38, orbit_y + 55, 9, 3))
    orbit = PROFILE["orbit"]
    for x, label, value in [
        (38, "DAYS IN ORBIT", f'{orbit["days"]} days'),
        (147, "LONGEST ORBIT", f'{orbit["longest_days"]} days'),
        (257, "REVOLUTIONS", orbit["revolutions_this_year"]),
    ]:
        p.append(text(x, orbit_y + 174, label, 7.6, fill="#aab6ce",
                      family=MONO, spacing=.1))
        p.append(text(x, orbit_y + 200, value, 16.5, weight=750))

    p.append(text(18, orbit_y + 285, "GitHub", 14.5, fill="#5fb6f8"))
    p.append(text(18, orbit_y + 321,
                  "Solar System · planets are languages", 10,
                  fill="#bfc7ca"))
    p.append(text(18, orbit_y + 337,
                  "comets are recent pushes · inspired by GitSkins",
                  10, fill="#bfc7ca"))
    if PROFILE.get("refreshed_on"):
        p.append(text(18, orbit_y + 354, f'updated {PROFILE["refreshed_on"]}',
                      9, fill=DIM, family=MONO))
    return document(390, height, "".join(p))


def readme() -> str:
    username = PROFILE["username"]
    projects = moons()
    user_url = "https://github.com/" + quote(username, safe="")
    language_summary = ", ".join(
        f'{item["name"]} {item["percent"]}%'
        for item in PROFILE["languages"][:4]
    ) or "none yet"
    project_summary = ", ".join(project["name"] for project in projects) or "none yet"
    alt = (
        f"Solar System profile for {username}. {PROFILE['bio']} "
        f"Featured projects: {project_summary}. Main languages: {language_summary}."
    )
    links = [f'<a href="{user_url}">GitHub</a>']
    for project in projects:
        project_url = user_url + "/" + quote(project["name"], safe="")
        links.append(f'<a href="{project_url}">{esc(project["name"])}</a>')
    link_line = " ·\n  ".join(links)
    return f"""<!-- Automatically refreshed by .github/workflows/refresh-profile.yml. -->

<div align="center">
  <picture>
    <source media="(max-width: 600px)" srcset="assets/solar-system-mobile.svg">
    <img src="assets/solar-system.svg" width="814" alt="{esc(alt)}">
  </picture>
</div>

<p align="center">
  {link_line}
</p>
"""


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "solar-system.svg").write_text(desktop(), encoding="utf-8")
    (ASSETS / "solar-system-mobile.svg").write_text(mobile(), encoding="utf-8")
    (ROOT / "README.md").write_text(readme(), encoding="utf-8")
    print("Generated README.md and desktop/mobile SVG artwork.")


if __name__ == "__main__":
    main()
