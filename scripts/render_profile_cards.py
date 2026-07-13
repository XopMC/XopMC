#!/usr/bin/env python3
"""Render GitHub profile SVG cards from public GraphQL data."""

from __future__ import annotations

import json
import math
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape


API_URL = "https://api.github.com/graphql"
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

BG = "#0d1117"
SURFACE = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
GREEN = "#3fb950"

LANGUAGE_COLORS = {
    "C++": "#f34b7d",
    "C": "#555555",
    "C#": "#178600",
    "CUDA": "#3A4E3A",
    "Cuda": "#3A4E3A",
    "Metal": "#8f14e9",
    "Objective-C++": "#6866fb",
    "Python": "#3572A5",
}

LANGUAGE_LABELS = {
    "Cuda": "CUDA",
    "Objective-C++": "Obj-C++",
}

PROFILE_LANGUAGES = (
    "C++",
    "C",
    "C#",
    "Python",
    "Cuda",
    "Objective-C++",
)

FEATURED_PROJECTS = (
    "METAL_CRYPTO_TOOLKIT",
    "C-Sharp-Mnemonic",
    "Mnemonic_CPP",
    "CUDA_Mnemonic_Recovery",
    "XorFilter",
    "TONc",
    "Metal_Mnemonic_Recovery",
    "keyhunt-win",
    "brainflayer-MultiBlooms",
    "brainflayer-CUDA",
)

QUERY = """
query ProfileCards($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, privacy: PUBLIC, ownerAffiliations: OWNER) {
      totalCount
      nodes {
        name
        stargazerCount
        primaryLanguage {
          name
          color
        }
      }
    }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
            weekday
          }
        }
      }
    }
  }
}
"""


def graphql(token: str, variables: dict[str, str]) -> dict:
    payload = json.dumps({"query": QUERY, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "XopMC-profile-card-renderer",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"GitHub GraphQL request failed: {exc}") from exc

    if result.get("errors"):
        messages = "; ".join(error.get("message", "unknown error") for error in result["errors"])
        raise RuntimeError(f"GitHub GraphQL returned errors: {messages}")
    user = result.get("data", {}).get("user")
    if not user:
        raise RuntimeError("GitHub user was not found")
    return user


def svg_start(width: int, height: int, label: str) -> list[str]:
    safe_label = escape(label)
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{safe_label}">',
        f"<title>{safe_label}</title>",
        "<style>",
        "text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }",
        ".mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }",
        "</style>",
        f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="12" fill="{BG}" stroke="{BORDER}" stroke-width="2"/>',
    ]


def write_svg(name: str, lines: list[str]) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    content = "\n".join([*lines, "</svg>", ""])
    (ASSETS / name).write_text(content, encoding="utf-8")


def format_count(value: int) -> str:
    return f"{value:,}"


def render_stats(user: dict) -> None:
    repositories = user["repositories"]
    stars = sum(repo["stargazerCount"] for repo in repositories["nodes"])
    contributions = user["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    values = [
        ("PUBLIC STARS", stars),
        ("REPOSITORIES", repositories["totalCount"]),
        ("FOLLOWERS", user["followers"]["totalCount"]),
        ("CONTRIBUTIONS", contributions),
    ]

    lines = svg_start(780, 270, "Live GitHub profile statistics")
    lines.append(f'<text x="34" y="43" fill="{GREEN}" font-size="24" font-weight="700">Profile statistics</text>')
    lines.append(f'<text x="746" y="42" fill="{MUTED}" font-size="12" text-anchor="end" class="mono">LIVE / 12 MONTHS</text>')

    positions = [(34, 72), (397, 72), (34, 158), (397, 158)]
    for (label, value), (x, y) in zip(values, positions):
        lines.append(f'<rect x="{x}" y="{y}" width="349" height="70" rx="7" fill="{SURFACE}" stroke="{BORDER}"/>')
        lines.append(f'<text x="{x + 18}" y="{y + 27}" fill="{MUTED}" font-size="12" font-weight="600" class="mono">{label}</text>')
        lines.append(f'<text x="{x + 18}" y="{y + 56}" fill="{TEXT}" font-size="27" font-weight="700">{format_count(value)}</text>')
    write_svg("stats.svg", lines)


def render_star_badges(user: dict) -> None:
    counts = {
        repository["name"]: repository["stargazerCount"]
        for repository in user["repositories"]["nodes"]
    }
    badge_dir = ASSETS / "stars"
    badge_dir.mkdir(parents=True, exist_ok=True)

    missing = [name for name in FEATURED_PROJECTS if name not in counts]
    if missing:
        raise RuntimeError(f"Featured public repositories were not found: {', '.join(missing)}")

    for name in FEATURED_PROJECTS:
        count = counts[name]
        label = f"★ {format_count(count)}"
        width = max(58, 24 + len(label) * 9)
        safe_label = escape(f"{name}: {format_count(count)} stars")
        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="24" viewBox="0 0 {width} 24" role="img" aria-label="{safe_label}">',
            f"<title>{safe_label}</title>",
            f'<rect x="0.5" y="0.5" width="{width - 1}" height="23" rx="6" fill="{SURFACE}" stroke="{BORDER}"/>',
            f'<text x="{width / 2:.1f}" y="16" fill="{TEXT}" font-size="12" font-weight="600" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">{escape(label)}</text>',
            "</svg>",
            "",
        ]
        (badge_dir / f"{name}.svg").write_text("\n".join(lines), encoding="utf-8")


def language_totals(user: dict) -> list[tuple[str, int, str]]:
    totals: dict[str, int] = defaultdict(int)
    api_colors: dict[str, str] = {}
    for repository in user["repositories"]["nodes"]:
        language = repository.get("primaryLanguage")
        if not language:
            continue
        name = language["name"]
        totals[name] += 1
        if language.get("color"):
            api_colors[name] = language["color"]

    return [
        (name, totals[name], LANGUAGE_COLORS.get(name, api_colors.get(name, GREEN)))
        for name in PROFILE_LANGUAGES
    ]


def render_languages(user: dict) -> None:
    languages = language_totals(user)
    lines = svg_start(780, 270, "Public repositories grouped by primary language")
    lines.append(f'<text x="34" y="43" fill="{GREEN}" font-size="24" font-weight="700">Languages by repository</text>')
    lines.append(f'<text x="746" y="42" fill="{MUTED}" font-size="12" text-anchor="end" class="mono">PUBLIC / CURRENT</text>')

    if not languages:
        lines.append(f'<text x="390" y="145" fill="{MUTED}" font-size="16" text-anchor="middle">No public commit data</text>')
        write_svg("languages.svg", lines)
        return

    chart_left = 36
    chart_top = 70
    chart_width = 708
    chart_height = 116
    gap = 12
    bar_width = (chart_width - gap * (len(languages) - 1)) / len(languages)
    maximum = max(count for _, count, _ in languages)
    lines.append(f'<line x1="{chart_left}" y1="{chart_top + chart_height}" x2="{chart_left + chart_width}" y2="{chart_top + chart_height}" stroke="{BORDER}"/>')

    for index, (name, count, color) in enumerate(languages):
        height = max(8, round(chart_height * count / maximum))
        x = chart_left + index * (bar_width + gap)
        y = chart_top + chart_height - height
        center = x + bar_width / 2
        label = LANGUAGE_LABELS.get(name, name)
        lines.append(f'<rect x="{x:.1f}" y="{y}" width="{bar_width:.1f}" height="{height}" rx="4" fill="{escape(color)}"/>')
        lines.append(f'<text x="{center:.1f}" y="{y - 7}" fill="{TEXT}" font-size="11" text-anchor="middle" class="mono">{format_count(count)}</text>')
        lines.append(f'<text x="{center:.1f}" y="{chart_top + chart_height + 22}" fill="{MUTED}" font-size="11" text-anchor="middle" class="mono">{escape(label)}</text>')

    lines.append(f'<text x="390" y="248" fill="{MUTED}" font-size="11" text-anchor="middle">Public repositories grouped by primary language</text>')
    write_svg("languages.svg", lines)


def activity_color(count: int, maximum: int) -> str:
    if count <= 0:
        return SURFACE
    if maximum <= 1:
        return "#39d353"
    ratio = math.log1p(count) / math.log1p(maximum)
    if ratio <= 0.25:
        return "#0e4429"
    if ratio <= 0.50:
        return "#006d32"
    if ratio <= 0.75:
        return "#26a641"
    return "#39d353"


def render_activity(user: dict) -> None:
    calendar = user["contributionsCollection"]["contributionCalendar"]
    weeks = calendar["weeks"]
    all_days = [day for week in weeks for day in week["contributionDays"]]
    maximum = max((day["contributionCount"] for day in all_days), default=0)

    width = 1580
    height = 320
    cell = 17
    gap = 5
    step = cell + gap
    grid_width = len(weeks) * step - gap
    grid_left = max(106, (width - grid_width) // 2)
    grid_top = 91

    lines = svg_start(width, height, "GitHub contribution activity during the last twelve months")
    lines.append(f'<text x="38" y="47" fill="{GREEN}" font-size="25" font-weight="700">Contribution activity</text>')
    lines.append(f'<text x="1542" y="46" fill="{TEXT}" font-size="14" text-anchor="end" class="mono">{format_count(calendar["totalContributions"])} CONTRIBUTIONS</text>')

    last_month = None
    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:
            date = datetime.strptime(day["date"], "%Y-%m-%d")
            if date.month != last_month and date.day <= 7:
                x = grid_left + week_index * step
                lines.append(f'<text x="{x}" y="75" fill="{MUTED}" font-size="12" class="mono">{date.strftime("%b")}</text>')
                last_month = date.month

            x = grid_left + week_index * step
            y = grid_top + day["weekday"] * step
            color = activity_color(day["contributionCount"], maximum)
            lines.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{color}" stroke="{BORDER}" stroke-width="0.5">'
                f'<title>{escape(day["date"])}: {day["contributionCount"]} contributions</title></rect>'
            )

    for label, weekday in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        y = grid_top + weekday * step + 13
        lines.append(f'<text x="{grid_left - 16}" y="{y}" fill="{MUTED}" font-size="12" text-anchor="end" class="mono">{label}</text>')

    first_date = all_days[0]["date"] if all_days else ""
    last_date = all_days[-1]["date"] if all_days else ""
    lines.append(f'<text x="38" y="292" fill="{MUTED}" font-size="11" class="mono">{escape(first_date)} / {escape(last_date)}</text>')
    legend_x = width - 230
    lines.append(f'<text x="{legend_x - 12}" y="292" fill="{MUTED}" font-size="11" text-anchor="end">Less</text>')
    for index, color in enumerate((SURFACE, "#0e4429", "#006d32", "#26a641", "#39d353")):
        lines.append(f'<rect x="{legend_x + index * 22}" y="278" width="17" height="17" rx="3" fill="{color}" stroke="{BORDER}" stroke-width="0.5"/>')
    lines.append(f'<text x="{legend_x + 121}" y="292" fill="{MUTED}" font-size="11">More</text>')
    write_svg("activity.svg", lines)


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 1

    login = os.environ.get("PROFILE_USER", "XopMC")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(days=364)
    user = graphql(
        token,
        {
            "login": login,
            "from": start.isoformat().replace("+00:00", "Z"),
            "to": now.isoformat().replace("+00:00", "Z"),
        },
    )
    render_stats(user)
    render_star_badges(user)
    render_languages(user)
    render_activity(user)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
