#!/usr/bin/env python3
"""Generate the animated GitHub profile banners (dark + light).

Run from the repository root:
    pip install -r scripts/banner/requirements.txt
    python scripts/banner/generate.py

VISUAL.MAP source
-----------------
* If assets/source/portrait.png exists (a head-and-shoulders photo, ideally
  with a TRANSPARENT background), it is dithered into the frame.
* Otherwise assets/source/monogram.png is used (built automatically on first
  run from a bold font).

The dots then morph: source -> React atom -> </> -> AI spark -> source.
Edit ROWS below to change the SYSTEM.INFO panel.
"""

from __future__ import annotations

import html
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "assets/source"
PORTRAIT = SRC_DIR / "portrait.png"
MONOGRAM = SRC_DIR / "monogram.png"
ASSETS = ROOT / "assets"
LOGOS = Path(__file__).resolve().parent / "logos"

VERSION = "v2"          # bump + update README <picture> paths to bust GitHub's cache
HANDLE = "@Bayartsetsegley01"

W, H = 1180, 610
LOOP_SECONDS = 14.2
INTRO_SECONDS = 3.2
TRAVELLER_COUNT = 900
MAX_DOTS = 60000  # keep every dither dot; random thinning blurs faces
SEED = 20260627

ROWS = [
    ("Subject", "Bayartsetseg · Баярцэцэг"),
    ("Role", "Software Developer"),
    ("Origin", "Ulaanbaatar, Mongolia"),
    ("Education", "MUST · B.Sc. IT · GPA 3.5"),
    ("Status", "Working as Software Developer"),
    ("Core.Lang", "TypeScript · JavaScript · Python · Java"),
    ("Core.Frontend", "React · Next.js · Tailwind · Vite"),
    ("Core.Mobile", "React Native · Expo"),
    ("Core.Backend", "Node · Express · Spring Boot"),
    ("Core.Database", "PostgreSQL · Supabase · Redis"),
    ("Core.AI", "LLM APIs · RAG · Tool Calling"),
    ("ToolChain", "Git · Docker · Postman · Figma"),
    ("Grid.Web", "bayartsetseg-portfolio.vercel.app"),
    ("Grid.Mail", "bayartsetsegley@gmail.com"),
    ("Grid.GitHub", "Bayartsetsegley01"),
]

FOOTER_LEFT = "● CURRENTLY WORKING · SOFTWARE DEVELOPER"
FOOTER_RIGHT = "UTC+8 · ULAANBAATAR NODE"

THEMES = {
    "dark": {
        "bg": "#0B0B1A",
        "panel": "#0F1024",
        "panel2": "#14162E",
        "line": "#2A2C4F",
        "muted": "#8B8FB5",
        "text": "#E4E6FA",
        "portrait": "#B69CFF",
        "chrome": "#67E8F9",
        "accent": "#34D399",
        "shadow": "#020208",
    },
    "light": {
        "bg": "#F6F7FB",
        "panel": "#FFFFFF",
        "panel2": "#F1EFFA",
        "line": "#D6D2EA",
        "muted": "#6B6788",
        "text": "#1C1A33",
        "portrait": "#5B3FD1",
        "chrome": "#0E7490",
        "accent": "#059669",
        "shadow": "#B7B2D4",
    },
}

MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #


def find_font(size: int) -> ImageFont.FreeTypeFont:
    for name in (
        "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def make_monogram() -> None:
    """A bold 'B' filled with a radial luminance gradient, so the 1-bit dither
    reads as texture instead of a flat blob. Transparent background."""
    size = (400, 452)
    grad = Image.new("L", size, 0)
    gx, gy = np.meshgrid(np.arange(size[0]), np.arange(size[1]))
    dist = np.hypot(gx - 150, gy - 150) / 360.0
    grad = Image.fromarray(np.uint8(np.clip(245 - dist * 150, 70, 245)), "L")

    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    font = find_font(390)
    bbox = d.textbbox((0, 0), "B", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size[0] - tw) / 2 - bbox[0], (size[1] - th) / 2 - bbox[1] - 6), "B",
           font=font, fill=255)
    # orbit ring + a small node: a nod to "systems thinking"
    d.ellipse((12, 38, 388, 414), outline=255, width=10)
    d.ellipse((330, 60, 372, 102), fill=255)

    rgb = Image.merge("RGB", (grad, grad, grad)).convert("RGBA")
    rgb.putalpha(mask)
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    rgb.save(MONOGRAM, optimize=True)


def make_logos() -> dict[str, Image.Image]:
    """400px black-on-transparent silhouettes."""
    LOGOS.mkdir(parents=True, exist_ok=True)
    size = 400
    logos: dict[str, Image.Image] = {}

    # React atom: three rotated orbits + nucleus.
    react = Image.new("L", (size, size), 0)
    for angle in (0, 60, 120):
        layer = Image.new("L", (size, size), 0)
        ImageDraw.Draw(layer).ellipse((22, 138, 378, 262), outline=255, width=20)
        react = Image.fromarray(np.maximum(
            np.asarray(react), np.asarray(layer.rotate(angle, resample=Image.BICUBIC))))
    ImageDraw.Draw(react).ellipse((168, 168, 232, 232), fill=255)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.putalpha(react)
    logos["react"] = img

    # </> mark.
    code = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(code)
    d.line([(154, 95), (66, 200), (154, 305)], fill="black", width=42, joint="curve")
    d.line([(246, 95), (334, 200), (246, 305)], fill="black", width=42, joint="curve")
    d.line([(225, 72), (174, 328)], fill="black", width=42)
    logos["code"] = code

    # AI spark: big four-point star + two small ones.
    spark = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(spark)

    def star(cx, cy, r, waist):
        pts = []
        for i in range(8):
            a = -math.pi / 2 + i * math.pi / 4
            rr = r if i % 2 == 0 else waist
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        d.polygon(pts, fill="black")

    star(180, 215, 150, 38)
    star(318, 92, 58, 15)
    star(330, 318, 36, 10)
    logos["spark"] = spark

    for name, image in logos.items():
        image.save(LOGOS / f"{name}.png", optimize=True)
    return logos


def floyd_steinberg(gray: np.ndarray) -> np.ndarray:
    """Serpentine 1-bit Floyd-Steinberg diffusion; True means a lit pixel."""
    work = gray.astype(np.float32) / 255.0
    out = np.zeros_like(work, dtype=bool)
    height, width = work.shape
    for y in range(height):
        ltr = y % 2 == 0
        xs = range(width) if ltr else range(width - 1, -1, -1)
        step = 1 if ltr else -1
        for x in xs:
            old = work[y, x]
            new = 1.0 if old >= 0.5 else 0.0
            out[y, x] = bool(new)
            err = old - new
            nx = x + step
            if 0 <= nx < width:
                work[y, nx] += err * 7 / 16
            if y + 1 < height:
                if 0 <= x - step < width:
                    work[y + 1, x - step] += err * 3 / 16
                work[y + 1, x] += err * 5 / 16
                if 0 <= nx < width:
                    work[y + 1, nx] += err * 1 / 16
    return out


def fit_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    """Cover-crop to w:h, biased toward the top (faces sit high in photos)."""
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    img = img.resize((round(sw * scale), round(sh * scale)), Image.Resampling.LANCZOS)
    left = (img.width - w) // 2
    top = min(max(0, round((img.height - h) * 0.2)), img.height - h)
    return img.crop((left, top, left + w, top + h))


def source_points(theme: str, rng: np.random.Generator) -> np.ndarray:
    """x/y banner coordinates from a 300x340 dither of the VISUAL.MAP source."""
    path = PORTRAIT if PORTRAIT.exists() else MONOGRAM
    crop = fit_crop(Image.open(path).convert("RGBA"), 300, 340)
    rgb = crop.convert("RGB")
    alpha = np.asarray(crop.getchannel("A"), dtype=np.float32) / 255.0
    has_alpha = alpha.min() < 0.99

    if theme == "dark":
        lum = np.asarray(ImageOps.grayscale(rgb), dtype=np.float32)
        prepared = Image.fromarray(np.uint8(np.clip(lum * alpha, 0, 255)), "L")
        if has_alpha:
            mask = Image.fromarray(np.uint8((alpha > 0.08) * 255), "L")
            prepared = ImageOps.equalize(prepared, mask=mask)
        else:
            prepared = ImageOps.equalize(prepared)
        select_lit = True
    else:
        white = Image.new("RGBA", crop.size, "white")
        white.alpha_composite(crop)
        gray = ImageOps.grayscale(white.convert("RGB"))
        if path == MONOGRAM:
            # invert so the letter (light in source) becomes dense ink on light bg
            gray = ImageOps.invert(gray)
            gray = Image.composite(gray, Image.new("L", gray.size, 255),
                                   Image.fromarray(np.uint8((alpha > 0.08) * 255), "L"))
        prepared = ImageOps.autocontrast(gray, cutoff=1)
        if path == PORTRAIT:
            # lift midtones so skin reads as light paper and only features ink in
            lut = [round(255 * (i / 255) ** 0.62) for i in range(256)]
            prepared = prepared.point(lut)
        select_lit = False

    prepared = ImageEnhance.Contrast(prepared).enhance(1.35)
    prepared = prepared.filter(ImageFilter.UnsharpMask(radius=2, percent=175, threshold=1))
    bits = floyd_steinberg(np.asarray(prepared))
    active = bits if select_lit else ~bits
    if has_alpha:
        active &= alpha > 0.08

    ys, xs = np.where(active)
    if len(xs) == 0:
        return np.zeros((0, 2), dtype=np.float32)
    points = np.column_stack((94 + xs, 161 + ys)).astype(np.float32)
    if len(points) > MAX_DOTS:
        points = points[rng.choice(len(points), MAX_DOTS, replace=False)]
    return points


def sample_logo_points(image: Image.Image, rng: np.random.Generator, count: int) -> np.ndarray:
    alpha = np.asarray(image.getchannel("A"))
    ys, xs = np.where(alpha > 127)
    chosen = rng.choice(len(xs), count, replace=len(xs) < count)
    return np.column_stack((109 + xs[chosen] * 0.675, 196 + ys[chosen] * 0.675)).astype(np.float32)


def transport(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    rows, cols = linear_sum_assignment(cdist(source, target, metric="sqeuclidean"))
    ordered = np.empty_like(target)
    ordered[rows] = target[cols]
    return ordered


# --------------------------------------------------------------------------- #
# svg
# --------------------------------------------------------------------------- #


def num(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def point_path(points: np.ndarray) -> str:
    """Merge horizontal runs of 1px dots into compact path segments."""
    if not len(points):
        return ""
    integer = np.rint(points).astype(int)
    unique = sorted({(int(x), int(y)) for x, y in integer}, key=lambda p: (p[1], p[0]))
    chunks: list[str] = []
    i = 0
    while i < len(unique):
        x0, y = unique[i]
        x1 = x0
        i += 1
        while i < len(unique) and unique[i][1] == y and unique[i][0] <= x1 + 1:
            x1 = unique[i][0]
            i += 1
        chunks.append(f"M{x0} {y}h{x1 - x0 + 1}")
    return "".join(chunks)


def dotted_leader(x1: float, x2: float, y: float) -> str:
    if x2 <= x1:
        return ""
    return "".join(f"M{x} {num(y)}h1" for x in np.arange(x1, x2, 5.0))


def text_width(text: str, font_size: float) -> float:
    return len(text) * font_size * 0.605


def animate_values(points: list[np.ndarray], index: int) -> str:
    return ";".join(f"{num(p[index, 0])} {num(p[index, 1])}" for p in points)


def mono(x, y, fill, size, body, extra=""):
    return (f'<text x="{num(x)}" y="{num(y)}" fill="{fill}" font-family="{MONO}" '
            f'font-size="{size}" {extra}>{body}</text>')


def render_svg(theme_name: str, source_pts: np.ndarray, logo_points: dict[str, np.ndarray],
               rng: np.random.Generator) -> str:
    t = THEMES[theme_name]
    n = min(TRAVELLER_COUNT, len(source_pts))
    source = source_pts[rng.choice(len(source_pts), n, replace=False)]
    react = transport(source, logo_points["react"][:n])
    code = transport(react, logo_points["code"][:n])
    spark = transport(code, logo_points["spark"][:n])

    times = [0, 3.0, 4.3, 6.3, 7.6, 9.6, 10.9, 12.9, 14.2]
    key_times = ";".join(num(v / LOOP_SECONDS) for v in times)
    frames = [source, source, react, react, code, code, spark, spark, source]
    opacity_values = "0;0;1;1;1;1;1;1;0"

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
        "<title id=\"title\">Bayartsetseg's live system profile</title>",
        '<desc id="desc">Animated terminal profile: a dithered portrait that morphs '
        "into React, code and AI silhouettes, next to a system-info panel.</desc>",
        "<defs>",
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">'
        f'<feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="{t["shadow"]}" '
        'flood-opacity=".28"/></filter>',
        '<filter id="glow" x="-100%" y="-100%" width="300%" height="300%">'
        f'<feGaussianBlur stdDeviation="3" result="b"/><feFlood flood-color="{t["chrome"]}" '
        'flood-opacity=".35"/><feComposite in2="b" operator="in"/>'
        '<feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
        f'<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{t["chrome"]}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{t["chrome"]}" stop-opacity=".14"/>'
        f'<stop offset="1" stop-color="{t["chrome"]}" stop-opacity="0"/></linearGradient>',
        '<clipPath id="visualClip"><rect x="49" y="124" width="390" height="414" rx="3"/></clipPath>',
        "</defs>",
        f'<rect width="{W}" height="{H}" rx="18" fill="{t["bg"]}"/>',
        f'<rect x="13" y="13" width="1154" height="584" rx="13" fill="{t["panel"]}" '
        f'stroke="{t["line"]}" filter="url(#shadow)"/>',
        f'<path d="M13 62H1167" stroke="{t["line"]}"/>',
        '<circle cx="38" cy="38" r="6" fill="#FF5F57"/>'
        '<circle cx="59" cy="38" r="6" fill="#FEBC2E"/>'
        '<circle cx="80" cy="38" r="6" fill="#28C840"/>',
        mono(590, 43, t["muted"], 13, "~/bayartsetseg $ ./profile.sh --live",
             'text-anchor="middle" letter-spacing=".4"'),
        # left frame
        f'<rect x="35" y="88" width="418" height="472" rx="6" fill="{t["panel2"]}" stroke="{t["line"]}"/>',
        f'<path d="M35 124H453" stroke="{t["line"]}"/>',
        mono(49, 111, t["chrome"], 13, "VISUAL.MAP", 'font-weight="700" letter-spacing="1.2"'),
        mono(438, 111, t["muted"], 11,
             ("ME" if PORTRAIT.exists() else "B") + " → REACT → &lt;/&gt; → AI", 'text-anchor="end"'),
        f'<path d="M49 141h12M49 141v12M439 141h-12M439 141v12M49 539h12M49 539v-12'
        f'M439 539h-12M439 539v-12" fill="none" stroke="{t["chrome"]}" opacity=".55"/>',
        '<g clip-path="url(#visualClip)" shape-rendering="crispEdges">',
        '<g opacity="1">',
    ]

    # dense source drift toward the React centroid
    centroid_t = react.mean(axis=0)
    band_ids = rng.integers(0, 94, size=len(source_pts))
    noise = rng.normal(0, 4, size=(94, 2))
    for band in range(94):
        pts = source_pts[band_ids == band]
        if not len(pts):
            continue
        delta = (centroid_t - pts.mean(axis=0)) * 0.18 + noise[band]
        parts.append(
            f'<path d="{point_path(pts)}" fill="none" stroke="{t["portrait"]}" stroke-width="1" '
            'opacity=".94">'
            f'<animateTransform attributeName="transform" type="translate" begin="{INTRO_SECONDS}s" '
            f'dur="{LOOP_SECONDS}s" repeatCount="indefinite" calcMode="linear" '
            f'keyTimes="{key_times}" values="0 0;0 0;{num(delta[0])} {num(delta[1])};'
            f'{num(delta[0])} {num(delta[1])};0 0;0 0;0 0;0 0;0 0"/>'
            f'<animate attributeName="opacity" begin="{INTRO_SECONDS}s" dur="{LOOP_SECONDS}s" '
            f'repeatCount="indefinite" keyTimes="{key_times}" '
            'values=".94;.94;0;0;0;0;0;0;.94"/></path>'
        )

    # optimal-transport travellers
    for i in range(n):
        parts.append(
            f'<path d="M-.65-.65h1.3v1.3h-1.3z" fill="{t["portrait"]}">'
            f'<animateTransform attributeName="transform" type="translate" begin="{INTRO_SECONDS}s" '
            f'dur="{LOOP_SECONDS}s" repeatCount="indefinite" calcMode="linear" '
            f'keyTimes="{key_times}" values="{animate_values(frames, i)}"/>'
            f'<animate attributeName="opacity" begin="{INTRO_SECONDS}s" dur="{LOOP_SECONDS}s" '
            f'repeatCount="indefinite" calcMode="linear" keyTimes="{key_times}" '
            f'values="{opacity_values}"/></path>'
        )
    parts.append("</g>")

    # one-shot scattered intro
    intro_ids = rng.integers(0, 60, size=len(source_pts))
    order = rng.permutation(60)
    starts = np.empty(60)
    starts[order] = np.linspace(0.05, 1.2, 60)
    for group in range(60):
        pts = source_pts[intro_ids == group]
        if not len(pts):
            continue
        parts.append(
            f'<path d="{point_path(pts)}" fill="none" stroke="{t["portrait"]}" '
            'stroke-width="1" opacity="0">'
            f'<animate attributeName="opacity" begin="{num(starts[group])}s" dur=".8s" '
            'values="0;1" fill="freeze"/>'
            '<animate attributeName="opacity" begin="3.08s" dur=".12s" values="1;0" fill="freeze"/>'
            "</path>"
        )

    # scan line sweeping the frame
    parts.append(
        '<rect x="49" y="-60" width="390" height="60" fill="url(#scan)">'
        '<animate attributeName="y" values="64;560" dur="4.8s" repeatCount="indefinite"/></rect>'
    )
    parts.append("</g>")

    parts.extend([
        mono(58, 551, t["muted"], 10, f"PTS {len(source_pts):05d} · FS/SERPENTINE"),
        # right panel
        f'<rect x="474" y="88" width="672" height="472" rx="6" fill="{t["panel2"]}" stroke="{t["line"]}"/>',
        f'<path d="M474 124H1146" stroke="{t["line"]}"/>',
        mono(490, 111, t["chrome"], 13, "SYSTEM.INFO", 'font-weight="700" letter-spacing="1.2"'),
        '<g filter="url(#glow)"><circle cx="868" cy="106" r="4" fill="#FF4D5A">'
        '<animate attributeName="opacity" values="1;.3;1" dur="1.6s" repeatCount="indefinite"/>'
        '</circle></g>',
        mono(880, 111, "#FF4D5A", 12, "LIVE", 'font-weight="700"'),
        f'<rect x="930" y="94" width="198" height="24" rx="12" fill="{t["chrome"]}" opacity=".16" '
        f'stroke="{t["chrome"]}"/>',
        mono(1029, 111, t["chrome"], 13, html.escape(HANDLE), 'text-anchor="middle" font-weight="700"'),
    ])

    value_right = 1127.0
    row_y = 153.0
    for idx, (label, value) in enumerate(ROWS):
        value_len = text_width(value, 14)
        label_len = text_width(label, 14)
        leader_start = 491 + label_len + 12
        leader_end = value_right - value_len - 12
        # rows type in one after another, like a boot log
        delay = 0.25 + idx * 0.12
        dur = delay + 0.25
        parts.append(
            f'<g><animate attributeName="opacity" dur="{dur:.2f}s" values="0;0;1" '
            f'keyTimes="0;{delay / dur:.3f};1" fill="freeze"/>'
            + mono(491, row_y, t["muted"], 14, html.escape(label))
            + f'<path d="{dotted_leader(leader_start, leader_end, row_y - 4)}" fill="none" '
            f'stroke="{t["line"]}" stroke-width="1" shape-rendering="crispEdges"/>'
            + mono(value_right, row_y, t["text"], 14, html.escape(value),
                   f'text-anchor="end" textLength="{num(value_len)}" lengthAdjust="spacingAndGlyphs"')
            + "</g>"
        )
        row_y += 23

    # blinking cursor after the last row
    parts.append(
        f'<rect x="491" y="{num(row_y - 13)}" width="8" height="15" fill="{t["chrome"]}">'
        '<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1s" '
        'repeatCount="indefinite"/></rect>'
    )

    parts.extend([
        f'<path d="M490 530H1130" stroke="{t["line"]}"/>',
        mono(491, 548, t["accent"], 11, html.escape(FOOTER_LEFT)),
        mono(1128, 548, t["muted"], 11, html.escape(FOOTER_RIGHT), 'text-anchor="end"'),
        "</svg>",
    ])
    return "".join(parts)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    if not PORTRAIT.exists() and not MONOGRAM.exists():
        make_monogram()
    logos = make_logos()
    print("source:", PORTRAIT.name if PORTRAIT.exists() else MONOGRAM.name)

    for index, theme in enumerate(THEMES):
        rng = np.random.default_rng(SEED + index)
        pts = source_points(theme, rng)
        rng = np.random.default_rng(SEED + 100 + index)
        sampled = {name: sample_logo_points(img, rng, TRAVELLER_COUNT) for name, img in logos.items()}
        svg = render_svg(theme, pts, sampled, rng)
        out = ASSETS / f"banner-{theme}.{VERSION}.svg"
        out.write_text(svg, encoding="utf-8")
        size = out.stat().st_size
        print(f"{out.relative_to(ROOT)}: {size / 1024:.1f} KiB, {len(pts):,} dots")


if __name__ == "__main__":
    main()
