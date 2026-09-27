#!/usr/bin/env python3
"""
cards.py - render project, stats and language cards as SVGs. Stdlib only.

Self-hosted replacement for github-readme-stats / top-langs / trophies, whose
shared public instances go down (503) or run out of quota (402). These are
files in your own repo, so they render as long as GitHub renders.

    python scripts/cards.py --user Bayartsetsegley01 --out assets
    python scripts/cards.py --offline            # project cards only (no API)

Writes
    card-project-<slug>-{dark,light}.svg   one per entry in assets/projects.json
    card-stats-{dark,light}.svg            stars / repos / followers (+ contributions)
    card-langs-{dark,light}.svg            language share across your own repos

A token in $GITHUB_TOKEN unlocks the contribution and streak tiles (GraphQL).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

UA = {"User-Agent": "cards.py"}
FONT = "ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

THEMES = {
    "dark": {
        "bg": "#0F1024", "border": "#2A2C4F", "title": "#E4E6FA",
        "text": "#C3C5E0", "muted": "#8B8FB5", "value": "#E4E6FA",
        "accent": "#B69CFF", "accent2": "#67E8F9", "pill": "#1B1D3A",
        "pill_text": "#C9BBFF", "track": "#1E2040",
    },
    "light": {
        "bg": "#FFFFFF", "border": "#D6D2EA", "title": "#1C1A33",
        "text": "#35324F", "muted": "#6B6788", "value": "#1C1A33",
        "accent": "#5B3FD1", "accent2": "#0E7490", "pill": "#F1EFFA",
        "pill_text": "#4A33B0", "track": "#ECEAF6",
    },
}

STATUS = {
    "live":        ("LIVE",        "#34D399", "#059669"),
    "in-progress": ("IN PROGRESS", "#FBBF24", "#B45309"),
    "open-source": ("OPEN SOURCE", "#67E8F9", "#0E7490"),
}

LANG_COLOR = {
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572A5",
    "HTML": "#e34c26", "CSS": "#663399", "Java": "#b07219", "Go": "#00ADD8",
    "Shell": "#89e051", "PLpgSQL": "#336790", "SCSS": "#c6538c", "Dockerfile": "#384d54",
    "Jupyter Notebook": "#DA5B0B", "Kotlin": "#A97BFF", "Swift": "#F05138",
    "C++": "#f34b7d", "C": "#555555", "Vue": "#41b883", "Other": "#8B8FB5",
}


# --------------------------------------------------------------------------- #
# api
# --------------------------------------------------------------------------- #


def rest(path: str, token: str | None):
    req = urllib.request.Request("https://api.github.com" + path, headers=dict(UA))
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def graphql(query: str, variables: dict, token: str):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                 headers={**UA, "Content-Type": "application/json",
                                          "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


CONTRIB_QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount } }
      }
    }
  }
}
"""


def fetch_contributions(user: str, token: str | None):
    """(total, current_streak, longest_streak) or None."""
    if not token:
        return None
    try:
        data = graphql(CONTRIB_QUERY, {"login": user}, token)
    except urllib.error.HTTPError as e:
        print(f"  contributions unavailable (HTTP {e.code})", file=sys.stderr)
        return None
    if data.get("errors"):
        print(f"  contributions unavailable: {data['errors'][0].get('message')}", file=sys.stderr)
        return None
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = sorted((dt.date.fromisoformat(d["date"]), d["contributionCount"])
                  for w in cal["weeks"] for d in w["contributionDays"])
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    current = 0
    for date, c in reversed(days):
        if c > 0:
            current += 1
        elif date != days[-1][0]:
            break
    return cal["totalContributions"], current, longest


# --------------------------------------------------------------------------- #
# svg helpers
# --------------------------------------------------------------------------- #


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def text_width(s: str, size: float) -> float:
    return len(s) * size * 0.53


def mono_width(s: str, size: float) -> float:
    return len(s) * size * 0.61


def wrap(text: str, size: float, max_w: float, max_lines: int, k: float = 0.53) -> list[str]:
    def tw(t):
        return len(t) * size * k
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if tw(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    used = len(" ".join(lines).split())
    if used < len(words) and lines:
        while lines and tw(lines[-1] + "…") > max_w:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] = lines[-1].rstrip(",.;:") + "…"
    return lines


def frame(w, h, c, body, label, uid):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{esc(label)}" font-family="{FONT}">'
        f'<defs><linearGradient id="g{uid}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{c["accent"]}"/><stop offset="1" stop-color="{c["accent2"]}"/>'
        f'</linearGradient><clipPath id="k{uid}"><rect width="{w}" height="{h}" rx="12"/></clipPath></defs>'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" '
        f'fill="{c["bg"]}" stroke="{c["border"]}"/>'
        f'<rect width="{w}" height="3" fill="url(#g{uid})" clip-path="url(#k{uid})"/>'
        f"{body}</svg>"
    )


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# --------------------------------------------------------------------------- #
# cards
# --------------------------------------------------------------------------- #


def render_project(p: dict, theme: str) -> str:
    c = THEMES[theme]
    W, H, pad = 430, 190, 20
    uid = slug(p["name"]) + theme
    out = []

    # category kicker
    out.append(f'<text x="{pad}" y="{pad + 16}" font-family="{MONO}" font-size="10.5" '
               f'letter-spacing="1.1" fill="{c["accent2"]}">{esc(p.get("category", "").upper())}</text>')

    # status pill
    label, dark_col, light_col = STATUS.get(p.get("status", "live"), STATUS["live"])
    col = dark_col if theme == "dark" else light_col
    pw = mono_width(label, 10) + 30
    px = W - pad - pw
    out.append(f'<rect x="{px:.0f}" y="{pad + 3}" width="{pw:.0f}" height="19" rx="9.5" '
               f'fill="{col}" fill-opacity=".12" stroke="{col}" stroke-opacity=".45"/>')
    out.append(f'<circle cx="{px + 11:.0f}" cy="{pad + 12.5}" r="3.2" fill="{col}">'
               + ('<animate attributeName="opacity" values="1;.35;1" dur="1.8s" repeatCount="indefinite"/>'
                  if p.get("status", "live") == "live" else "")
               + "</circle>")
    out.append(f'<text x="{px + 20:.0f}" y="{pad + 16.5}" font-family="{MONO}" font-size="10" '
               f'font-weight="700" fill="{col}">{label}</text>')

    # title
    out.append(f'<text x="{pad}" y="{pad + 46}" font-size="19" font-weight="700" '
               f'fill="{c["title"]}">{esc(p["name"])}</text>')

    # tagline + description
    out.append(f'<text x="{pad}" y="{pad + 66}" font-size="12" font-weight="600" '
               f'fill="{c["accent"]}">{esc(p.get("tagline", ""))}</text>')
    for i, line in enumerate(wrap(p.get("description", ""), 11.5, W - 2 * pad, 3, 0.47)):
        out.append(f'<text x="{pad}" y="{pad + 88 + i * 16}" font-size="11.5" '
                   f'fill="{c["text"]}">{esc(line)}</text>')

    # tech pills
    x, y = pad, H - pad - 18
    for tag in p.get("tags", []):
        tw = mono_width(tag, 10.5) + 14
        if x + tw > W - pad - 30:
            break
        out.append(f'<rect x="{x:.0f}" y="{y}" width="{tw:.0f}" height="20" rx="6" fill="{c["pill"]}"/>')
        out.append(f'<text x="{x + tw / 2:.1f}" y="{y + 14}" text-anchor="middle" font-family="{MONO}" '
                   f'font-size="10.5" fill="{c["pill_text"]}">{esc(tag)}</text>')
        x += tw + 6

    # "open" arrow, bottom-right
    out.append(f'<path transform="translate({W - pad - 14},{y + 3})" d="M2 12 12 2M4.5 2H12v7.5" '
               f'fill="none" stroke="{c["accent"]}" stroke-width="1.8" stroke-linecap="round" '
               f'stroke-linejoin="round"/>')

    return frame(W, H, c, "".join(out), f'{p["name"]} project card', uid)


CARD_H = 206  # stats + languages cards share a height so they sit side by side


def render_stats(user, tiles, theme):
    c = THEMES[theme]
    pad, cols, rh, W = 22, 3, 54, 460
    rows = (len(tiles) + cols - 1) // cols
    H = max(CARD_H, pad + 58 + (rows - 1) * rh + 18 + pad)
    tw = (W - 2 * pad) / cols
    out = [
        f'<text x="{pad}" y="{pad + 16}" font-family="{MONO}" font-size="13" font-weight="700" '
        f'fill="{c["accent"]}">$ gh stats {esc(user)}</text>',
        f'<line x1="{pad}" y1="{pad + 30}" x2="{W - pad}" y2="{pad + 30}" stroke="{c["border"]}"/>',
    ]
    block = (rows - 1) * rh + 17 + 24
    area_top, area_bot = pad + 30, H - pad + 6
    top = area_top + (area_bot - area_top - block) / 2 + 24
    for i, (label, value) in enumerate(tiles):
        cx = pad + (i % cols) * tw
        cy = top + (i // cols) * rh
        out.append(f'<text x="{cx:.0f}" y="{cy:.0f}" font-size="24" font-weight="700" '
                   f'fill="{c["value"]}">{esc(value)}</text>')
        out.append(f'<text x="{cx:.0f}" y="{cy + 17:.0f}" font-size="10.5" '
                   f'fill="{c["muted"]}">{esc(label)}</text>')
    return frame(W, H, c, "".join(out), f"{user} GitHub statistics", "stats" + theme)


def render_langs(shares, theme, note=""):
    """shares: list of (language, percent) summing to ~100."""
    c = THEMES[theme]
    pad, W = 22, 460
    rows = (len(shares) + 1) // 2
    H = max(CARD_H, pad + 30 + 14 + 14 + 22 + rows * 22 + pad - 6)
    out = [
        f'<text x="{pad}" y="{pad + 16}" font-family="{MONO}" font-size="13" font-weight="700" '
        f'fill="{c["accent"]}">$ cat languages.log</text>',
        f'<line x1="{pad}" y1="{pad + 30}" x2="{W - pad}" y2="{pad + 30}" stroke="{c["border"]}"/>',
    ]
    by = pad + 44
    bw = W - 2 * pad
    out.append(f'<clipPath id="bar{theme}"><rect x="{pad}" y="{by}" width="{bw}" height="10" rx="5"/></clipPath>')
    out.append(f'<rect x="{pad}" y="{by}" width="{bw}" height="10" rx="5" fill="{c["track"]}"/>')
    x = pad
    out.append(f'<g clip-path="url(#bar{theme})">')
    for name, pct in shares:
        w = bw * pct / 100
        out.append(f'<rect x="{x:.1f}" y="{by}" width="{w + 0.5:.1f}" height="10" '
                   f'fill="{LANG_COLOR.get(name, c["muted"])}"/>')
        x += w
    out.append("</g>")
    ly = by + 36
    for i, (name, pct) in enumerate(shares):
        cx = pad + (i % 2) * (bw / 2)
        cy = ly + (i // 2) * 22
        out.append(f'<circle cx="{cx + 5:.0f}" cy="{cy - 4}" r="5" fill="{LANG_COLOR.get(name, c["muted"])}"/>')
        out.append(f'<text x="{cx + 16:.0f}" y="{cy}" font-size="12" fill="{c["text"]}">{esc(name)}</text>')
        out.append(f'<text x="{cx + bw / 2 - 18:.0f}" y="{cy}" text-anchor="end" font-family="{MONO}" '
                   f'font-size="11.5" fill="{c["muted"]}">{pct:.1f}%</text>')
    if note:
        out.append(f'<text x="{W - pad}" y="{pad + 16}" text-anchor="end" font-size="10.5" '
                   f'fill="{c["muted"]}">{esc(note)}</text>')
    return frame(W, H, c, "".join(out), "most used languages", "langs" + theme)


# --------------------------------------------------------------------------- #


def write_pair(out: Path, stem: str, fn):
    for theme in ("dark", "light"):
        (out / f"{stem}-{theme}.svg").write_text(fn(theme), encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--user", default="Bayartsetsegley01")
    p.add_argument("--out", type=Path, default=Path("assets"))
    p.add_argument("--projects", type=Path, default=Path("assets/projects.json"))
    p.add_argument("--offline", action="store_true",
                   help="project cards only; placeholder stats/langs if missing")
    p.add_argument("--exclude", default="",
                   help="comma-separated languages to leave out of the language card")
    args = p.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    # ---- project cards (no API needed) ----
    if args.projects.exists():
        for proj in json.loads(args.projects.read_text(encoding="utf-8"))["projects"]:
            stem = f"card-project-{slug(proj['name'])}"
            write_pair(args.out, stem, lambda t, proj=proj: render_project(proj, t))
            print(f"wrote {stem}-*.svg")

    if args.offline:
        if not (args.out / "card-stats-dark.svg").exists():
            tiles = [("Public repos", "—"), ("Total stars", "—"), ("Followers", "—")]
            write_pair(args.out, "card-stats", lambda t: render_stats(args.user, tiles, t))
        if not (args.out / "card-langs-dark.svg").exists():
            shares = [("TypeScript", 40.0), ("JavaScript", 25.0), ("Java", 15.0),
                      ("Python", 8.0), ("CSS", 7.0), ("Other", 5.0)]
            write_pair(args.out, "card-langs", lambda t: render_langs(shares, t, "placeholder"))
        return

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    user = rest(f"/users/{args.user}", token)
    repos, page = [], 1
    while True:
        batch = rest(f"/users/{args.user}/repos?per_page=100&page={page}&type=owner", token)
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    owned = [r for r in repos if not r["fork"] and not r.get("archived")]

    # ---- stats ----
    tiles = [("Public repos", f"{user['public_repos']:,}"),
             ("Total stars", f"{sum(r['stargazers_count'] for r in owned):,}"),
             ("Followers", f"{user['followers']:,}")]
    contrib = fetch_contributions(args.user, token)
    if contrib:
        total, current, longest = contrib
        tiles += [("Contributions (1y)", f"{total:,}"),
                  ("Current streak", f"{current:,} d"),
                  ("Longest streak", f"{longest:,} d")]
    write_pair(args.out, "card-stats", lambda t: render_stats(args.user, tiles, t))
    print(f"wrote card-stats-*.svg ({len(tiles)} tiles)")

    # ---- languages ----
    exclude = {s.strip().lower() for s in args.exclude.split(",") if s.strip()}
    totals: dict[str, int] = {}
    for r in owned:
        if r["name"].lower() == args.user.lower():
            continue  # skip this profile repo itself
        try:
            langs = rest(f"/repos/{args.user}/{r['name']}/languages", token)
        except urllib.error.HTTPError:
            continue
        for name, n in langs.items():
            if name.lower() not in exclude:
                totals[name] = totals.get(name, 0) + n
    if totals:
        s = sum(totals.values())
        ranked = sorted(totals.items(), key=lambda kv: -kv[1])
        top = [(n, 100 * b / s) for n, b in ranked[:7]]
        rest_pct = 100 - sum(p for _, p in top)
        if rest_pct >= 0.1:
            top.append(("Other", rest_pct))
        write_pair(args.out, "card-langs", lambda t: render_langs(top, t, "by bytes, own repos"))
        print(f"wrote card-langs-*.svg ({len(top)} languages)")


if __name__ == "__main__":
    main()
