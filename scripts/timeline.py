#!/usr/bin/env python3
"""
timeline.py - render an animated horizontal journey timeline as SVG. Stdlib only.

    python scripts/timeline.py --data assets/journey.json -o assets/journey

journey.json shape:
    { "milestones": [ {"year": "2022", "title": "...", "items": ["...", "..."]}, ... ] }

The last milestone is marked as "now" with a pulsing ring.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FONT = "ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

THEMES = {
    "dark": {"line": "#2A2C4F", "year": "#E4E6FA", "title": "#B69CFF", "text": "#C3C5E0",
             "muted": "#8B8FB5", "node": "#B69CFF", "node2": "#67E8F9", "bg": "#0F1024"},
    "light": {"line": "#D6D2EA", "year": "#1C1A33", "title": "#5B3FD1", "text": "#35324F",
              "muted": "#6B6788", "node": "#5B3FD1", "node2": "#0E7490", "bg": "#FFFFFF"},
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap(text: str, size: float, max_w: float) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if len(trial) * size * 0.5 <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render(ms: list[dict], theme: str, width: int) -> str:
    c = THEMES[theme]
    n = len(ms)
    pad = 24
    col = (width - 2 * pad) / n
    line_y = 64
    body_top = line_y + 40
    step = 0.45  # seconds between milestones

    # lay out text first to size the canvas
    blocks, max_bottom = [], body_top
    for m in ms:
        y = body_top
        rows = []
        for ln in wrap(m.get("title", ""), 12.5, col - 18):
            rows.append(("title", ln, y))
            y += 17
        y += 4
        for item in m.get("items", []):
            first = True
            for ln in wrap(item, 11.5, col - 30):
                rows.append(("item" if first else "cont", ln, y))
                first = False
                y += 15.5
            y += 5
        blocks.append(rows)
        max_bottom = max(max_bottom, y)
    H = round(max_bottom + pad - 6)

    x0, x1 = pad + col / 2, width - pad - col / 2
    length = x1 - x0
    total = step * (n - 1) + 0.6
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {H}" width="{width}" '
        f'height="{H}" role="img" aria-label="career journey timeline" font-family="{FONT}">',
        f'<defs><linearGradient id="tl{theme}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{c["node"]}"/><stop offset="1" stop-color="{c["node2"]}"/>'
        f'</linearGradient></defs>',
        # base track + animated progress line
        f'<line x1="{x0:.1f}" y1="{line_y}" x2="{x1:.1f}" y2="{line_y}" stroke="{c["line"]}" stroke-width="2"/>',
        f'<line x1="{x0:.1f}" y1="{line_y}" x2="{x1:.1f}" y2="{line_y}" stroke="url(#tl{theme})" '
        f'stroke-width="3" stroke-linecap="round" stroke-dasharray="{length:.1f}" '
        f'stroke-dashoffset="{length:.1f}"><animate attributeName="stroke-dashoffset" '
        f'from="{length:.1f}" to="0" dur="{total:.2f}s" fill="freeze" calcMode="spline" '
        f'keyTimes="0;1" keySplines="0.4 0 0.2 1"/></line>',
    ]

    for i, (m, rows) in enumerate(zip(ms, blocks)):
        cx = pad + col * i + col / 2
        left = pad + col * i + 9
        last = i == n - 1
        # static opacity stays 1 so non-SMIL renderers still show everything;
        # the animation holds 0 until its own delay, then fades in.
        delay = 0.15 + i * step
        dur = delay + 0.45
        g = [f'<g><animate attributeName="opacity" dur="{dur:.2f}s" values="0;0;1" '
             f'keyTimes="0;{delay / dur:.3f};1" fill="freeze"/>']
        g.append(f'<text x="{cx:.1f}" y="{line_y - 22}" text-anchor="middle" font-family="{MONO}" '
                 f'font-size="17" font-weight="700" fill="{c["year"]}">{esc(m["year"])}</text>')
        if last:
            g.append(f'<circle cx="{cx:.1f}" cy="{line_y}" r="7" fill="none" stroke="{c["node2"]}" '
                     f'stroke-width="2"><animate attributeName="r" values="7;15" dur="1.8s" '
                     f'repeatCount="indefinite"/><animate attributeName="opacity" values=".9;0" '
                     f'dur="1.8s" repeatCount="indefinite"/></circle>')
            g.append(f'<text x="{cx + 20:.1f}" y="{line_y + 4}" font-family="{MONO}" font-size="10" '
                     f'font-weight="700" letter-spacing="1" fill="{c["node2"]}">NOW</text>')
        g.append(f'<circle cx="{cx:.1f}" cy="{line_y}" r="7" fill="{c["bg"]}" '
                 f'stroke="{c["node2"] if last else c["node"]}" stroke-width="3"/>')
        g.append(f'<circle cx="{cx:.1f}" cy="{line_y}" r="2.6" fill="{c["node2"] if last else c["node"]}"/>')
        g.append(f'<line x1="{cx:.1f}" y1="{line_y + 12}" x2="{cx:.1f}" y2="{body_top - 12}" '
                 f'stroke="{c["line"]}" stroke-dasharray="2 3"/>')
        for kind, text, y in rows:
            if kind == "title":
                g.append(f'<text x="{left:.1f}" y="{y:.1f}" font-size="12.5" font-weight="700" '
                         f'fill="{c["title"]}">{esc(text)}</text>')
            else:
                if kind == "item":
                    g.append(f'<rect x="{left + 1:.1f}" y="{y - 7.5:.1f}" width="5" height="5" rx="1" '
                             f'fill="{c["muted"]}"/>')
                g.append(f'<text x="{left + 13:.1f}" y="{y:.1f}" font-size="11.5" '
                         f'fill="{c["text"]}">{esc(text)}</text>')
        g.append("</g>")
        parts.append("".join(g))

    parts.append("</svg>")
    return "".join(parts)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("assets/journey.json"))
    p.add_argument("-o", "--out", type=Path, default=Path("assets/journey"))
    p.add_argument("--width", type=int, default=900)
    args = p.parse_args(argv)
    ms = json.loads(args.data.read_text(encoding="utf-8"))["milestones"]
    for theme in ("dark", "light"):
        dest = args.out.with_name(f"{args.out.name}-{theme}.svg")
        dest.write_text(render(ms, theme, args.width), encoding="utf-8")
        print(f"wrote {dest}  ({len(ms)} milestones)")


if __name__ == "__main__":
    main()
