"""Render the profile README's neofetch-style card as light and dark SVGs."""

import base64
import math
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent

NAME = "Brendan Barnes"
# Each group is separated by a blank line. A label of "" continues the line above.
INFO = [
    [
        ("OS", "Software Engineer"),
        ("Host", "St. Paul, Minnesota"),
        ("Kernel", "Geospatial Systems"),
        ("Uptime", None),  # filled in by uptime()
    ],
    [
        ("CPU", "Backend Services"),
        ("GPU", "Data Visualization"),
        ("Memory", "Spatial Databases"),
        ("Disk", "Cloud Infrastructure"),
    ],
    [
        ("Theme", "Open Source"),
        ("Packages", "Python, Rust, PostGIS,"),
        ("", "AWS, Docker, Terraform, Linux"),
    ],
    [
        ("Contact", "brendan.barnes856@gmail.com"),
    ],
]

THEMES = {
    "dark": {
        "bg": "#0d1117",
        "bar": "#161b22",
        "btn": "#2d333b",
        "border": "#30363d",
        "fg": "#c9d1d9",
        "muted": "#8b949e",
        "accent": "#58a6ff",
        "name": "#e6edf3",
        "prompt": "#3fb950",
        "vibe": "#d2a8ff",
        "ocean": "#388bfd",
        "land": "#3fb950",
        "home": "#ff7b72",
        # Terminal palette, in order: black red green yellow blue magenta cyan white.
        "night": "#0d1117",
        "land_levels": (0.22, 0.5, 0.75, 1.0),
        "ocean_levels": (0.08, 0.18, 0.28, 0.4),
        "ansi": ["#484f58", "#ff7b72", "#3fb950", "#d29922", "#58a6ff", "#bc8cff", "#39c5cf", "#b1bac4"],
        "bright": ["#6e7681", "#ffa198", "#56d364", "#e3b341", "#79c0ff", "#d2a8ff", "#56d4dd", "#ffffff"],
    },
    "light": {
        "bg": "#ffffff",
        "bar": "#f6f8fa",
        "btn": "#e6e8eb",
        "border": "#d0d7de",
        "fg": "#24292f",
        "muted": "#57606a",
        "accent": "#0969da",
        "name": "#1f2328",
        "prompt": "#1a7f37",
        "vibe": "#8250df",
        "ocean": "#5a8ee8",
        "land": "#5aa65a",
        "home": "#cf222e",
        # Terminal palette, in order: black red green yellow blue magenta cyan white.
        # One Light's terminal colors: unlike GitHub's light palette, yellow stays yellow on white.
        "ansi": ["#383a42", "#e45649", "#50a14f", "#c18401", "#4078f2", "#a626a4", "#0184bc", "#a0a1a7"],
        "bright": ["#696c77", "#f07178", "#8cc265", "#e5c07b", "#61afef", "#c678dd", "#56b6c2", "#d4d5d9"],
        "night": "#3a4660",
        "land_levels": (0.45, 0.66, 0.84, 1.0),
        "ocean_levels": (0.4, 0.62, 0.8, 1.0),
    },
}

# VT323 (DEC VT320 lettering), embedded. Its advance width is 0.4em, so text lines up on a grid.
FONT = "'Card Mono', 'VT323', ui-monospace, monospace"
FONT_SIZE = 20
CHAR_W = FONT_SIZE * 0.4
PAD = 32
BAR_H = 36
LINE_H = 22
WIDTH = 920

# Globe: a pixel-art Earth that spins, with St. Paul marked.
GLOBE_CELLS = 38          # diameter in pixels
GLOBE_PX = 8              # size of one pixel on the card
FRAMES = 36               # 10 degrees of rotation per frame
SPIN_SECONDS = 14
TILT = math.radians(23.4)
LIGHT = (-0.55, 0.45, 0.70)
HOME = (44.95, -93.09)    # St. Paul, MN


def _load_land():
    rows = [r for r in (ROOT / "earth.txt").read_text().splitlines() if not r.startswith("#")]
    return [[c == "#" for c in r] for r in rows]


def _is_land(land, lat, lon):
    h, w = len(land), len(land[0])
    r = min(h - 1, int((90 - lat) / 180 * h))
    c = int(((lon + 180) % 360) / 360 * w) % w
    return land[r][c]


def _globe_frame(land, spin):
    """Return {(kind, level): [(row, col_start, length)]} and the home pixel, if visible."""
    n = GLOBE_CELLS
    rad = n / 2
    lx, ly, lz = LIGHT
    ln = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / ln, ly / ln, lz / ln
    ct, st = math.cos(TILT), math.sin(TILT)
    cells = {}
    for j in range(n):
        for i in range(n):
            x = (i + 0.5 - rad) / rad
            y = (rad - (j + 0.5)) / rad
            d = x * x + y * y
            if d > 1:
                continue
            z = math.sqrt(1 - d)
            b = x * lx + y * ly + z * lz
            level = 0 if b < 0.08 else 1 if b < 0.4 else 2 if b < 0.7 else 3
            # Undo the axial tilt (a rotation in the screen plane), then read lat/lon.
            gx, gy = x * ct + y * st, -x * st + y * ct
            lat = math.degrees(math.asin(max(-1.0, min(1.0, gy))))
            lon = math.degrees(math.atan2(gx, z)) + spin
            kind = "land" if _is_land(land, lat, lon) else "ocean"
            cells[(j, i)] = (kind, level)

    runs = {}
    for j in range(n):
        i = 0
        while i < n:
            key = cells.get((j, i))
            start = i
            while i < n and cells.get((j, i)) == key:
                i += 1
            if key:
                runs.setdefault(key, []).append((j, start, i - start))

    # Where St. Paul lands on screen this frame.
    lat, lon = math.radians(HOME[0]), math.radians(HOME[1] - spin)
    gx, gy, z = math.cos(lat) * math.sin(lon), math.sin(lat), math.cos(lat) * math.cos(lon)
    home = None
    if z > 0.15:
        x, y = gx * ct - gy * st, gx * st + gy * ct
        home = (int(rad - y * rad), int(x * rad + rad))
    return runs, home


def _blend(a, b, t):
    """Mix hex colors a and b; t=0 gives a, t=1 gives b."""
    pa = [int(a[k:k + 2], 16) for k in (1, 3, 5)]
    pb = [int(b[k:k + 2], 16) for k in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def _globe(theme, x0, y0):
    land = _load_land()
    step = 100 / FRAMES
    css = (
        f".f{{opacity:0;animation:spin {SPIN_SECONDS}s step-end infinite}} .f0{{opacity:1}}"
        f"@keyframes spin{{0%,{step:.3f}%{{opacity:1}}{step + 0.001:.3f}%,100%{{opacity:0}}}}"
        "@media (prefers-reduced-motion:reduce){.f{animation:none}}"
    )
    frames = []
    for f in range(FRAMES):
        # Frame 0 faces home, so the static fallback shows St. Paul.
        runs, home = _globe_frame(land, HOME[1] - f * 360 / FRAMES)
        paths = []
        for (kind, level), rs in sorted(runs.items()):
            # Blend from the night color toward the full color as the light increases. Solid fills
            # (not opacity) so the night side is dark on any background.
            fill = _blend(theme["night"], theme[kind], theme[f"{kind}_levels"][level])
            d = "".join(f"M{c} {r}h{w}v1h-{w}z" for r, c, w in rs)
            paths.append(f'<path d="{d}" fill="{fill}"/>')
        if home:
            r, c = home
            paths.append(f'<rect x="{c}" y="{r}" width="1" height="1" fill="{theme["home"]}"/>')
        delay = f * SPIN_SECONDS / FRAMES - SPIN_SECONDS
        frames.append(f'<g class="f f{f}" style="animation-delay:{delay:.3f}s">{"".join(paths)}</g>')
    r = GLOBE_CELLS / 2
    outline = f'<circle cx="{r}" cy="{r}" r="{r + 0.4}" fill="none" stroke="{theme["border"]}" stroke-width="0.25"/>'
    body = outline + "\n" + "\n".join(frames)
    return css, f'<g transform="translate({x0} {y0}) scale({GLOBE_PX})" shape-rendering="crispEdges">\n{body}\n</g>'


# Palette bars: the 8 terminal colors as a little terminal bar chart. Bars sit on the character
# grid (3 cells wide), are drawn as scanline strips with a lit cap, and cast a dithered drop
# shadow like an old DOS text UI. Each color's short name sits underneath.
BAR_CELLS = 3             # bar width, in characters
BAR_STRIP = 4             # scanline pitch: 3px strip, 1px gap
BAR_RISE = (3, 5, 8, 6, 10, 8, 12, 10)  # bar heights, in strips
BAR_NAMES = ("blk", "red", "grn", "ylw", "blu", "mag", "cyn", "wht")
SHADOW = 4                # drop shadow offset, px


def _luminance(hex_color):
    r, g, b = (int(hex_color[k:k + 2], 16) for k in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _bars(theme, x0, y0):
    w = BAR_CELLS * CHAR_W
    tallest = max(BAR_RISE) * BAR_STRIP
    base = y0 + tallest  # bottom edge of every bar
    shadows, bars, names = [], [], []
    for k, pair in enumerate(zip(theme["ansi"], theme["bright"])):
        side, lit = sorted(pair, key=_luminance)
        x = x0 + k * (BAR_CELLS + 1) * CHAR_W
        strips = BAR_RISE[k]
        top = base - strips * BAR_STRIP
        shadows.append(f'<rect x="{x + SHADOW}" y="{top + SHADOW}" width="{w}" height="{strips * BAR_STRIP}"/>')
        for n in range(strips):
            color = lit if n == 0 else side
            bars.append(f'<rect x="{x}" y="{top + n * BAR_STRIP}" width="{w}" height="{BAR_STRIP - 1}" fill="{color}"/>')
        names.append(f'<text x="{x}" y="{base + SHADOW + FONT_SIZE}" class="dim">{BAR_NAMES[k]}</text>')
    svg = (
        f'<defs><pattern id="dither" width="2" height="2" patternUnits="userSpaceOnUse">'
        f'<rect width="1" height="1" fill="{theme["fg"]}"/><rect x="1" y="1" width="1" height="1" fill="{theme["fg"]}"/>'
        f'</pattern></defs>'
        f'<g fill="url(#dither)" opacity="0.35">{"".join(shadows)}</g>'
        + "".join(bars) + "".join(names)
    )
    return svg, tallest + SHADOW + FONT_SIZE


def _font_faces():
    """Embed the VT323 subset, since an SVG shown as an image can't load outside fonts."""
    data = base64.b64encode((ROOT / "assets" / "fonts" / "VT323-Regular.woff2").read_bytes()).decode()
    return (f"@font-face {{ font-family: 'Card Mono'; "
            f"src: url(data:font/woff2;base64,{data}) format('woff2'); }}")


PROMPT = "barne856@github ~> whoami "

CAREER_START = date(2018, 5, 1)


def uptime(today=None):
    """Whole years since CAREER_START; ticks over each May."""
    today = today or date.today()
    years = today.year - CAREER_START.year - ((today.month, today.day) < (CAREER_START.month, CAREER_START.day))
    return f"{years} year{'s' if years != 1 else ''}"


def render(vibe: str, theme_name: str) -> str:
    t = THEMES[theme_name]
    art = GLOBE_CELLS * GLOBE_PX

    prompt_y = BAR_H + 34
    body_y = prompt_y + 26
    info_x = PAD + art + 52
    label_w = 10 * CHAR_W

    parts = []
    y = body_y + 16
    parts.append(f'<text x="{info_x}" y="{y}" class="name">{escape(NAME)}</text>')
    y += 10
    parts.append(f'<line x1="{info_x}" y1="{y}" x2="{WIDTH - PAD}" y2="{y}" stroke="{t["border"]}"/>')
    y += 8

    groups = [[(k, uptime() if k == "Uptime" else v) for k, v in g] for g in INFO]
    groups[-1].insert(0, ("Vibe", vibe))
    for g in groups:
        for label, value in g:
            y += LINE_H
            if label:
                parts.append(f'<text x="{info_x}" y="{y}" class="label">{escape(label)}</text>')
            cls = "vibe" if label == "Vibe" else "value"
            parts.append(f'<text x="{info_x + label_w}" y="{y}" class="{cls}">{escape(value)}</text>')
        y += LINE_H // 2

    y += 10
    bars, bars_h = _bars(t, info_x, y)
    parts.append(bars)

    height = max(body_y + art, y + bars_h) + PAD
    globe_y = body_y + (height - PAD - body_y - art) // 2
    globe_css, globe = _globe(t, PAD, globe_y)
    # GNOME-style window buttons on the right: minimize, maximize, close.
    cy = BAR_H / 2
    bx = [WIDTH - 82, WIDTH - 54, WIDTH - 26]
    s = f'stroke="{t["fg"]}" stroke-width="1.4" fill="none" stroke-linecap="round"'
    dots = "".join(f'<circle cx="{x}" cy="{cy}" r="10" fill="{t["btn"]}"/>' for x in bx) + (
        f'<path d="M{bx[0] - 4} {cy} h8" {s}/>'
        f'<rect x="{bx[1] - 4}" y="{cy - 4}" width="8" height="8" rx="1" {s}/>'
        f'<path d="M{bx[2] - 4} {cy - 4} l8 8 M{bx[2] + 4} {cy - 4} l-8 8" {s}/>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(NAME)}: software engineer in St. Paul, Minnesota, working on geospatial systems. Today's vibe: {escape(vibe)}">
<style>
{_font_faces()}
text {{ font-family: {FONT}; font-size: {FONT_SIZE}px; fill: {t["fg"]}; font-variant-ligatures: none; }}
.name {{ font-size: {FONT_SIZE * 1.4:g}px; fill: {t["name"]}; }}
.label {{ fill: {t["accent"]}; }}
.dim {{ fill: {t["muted"]}; }}
.vibe {{ fill: {t["vibe"]}; }}
.title {{ fill: {t["fg"]}; font-size: 18px; }}
.user {{ fill: {t["prompt"]}; }}
.cwd {{ fill: {t["prompt"]}; }}
.cursor {{ animation: blink 1.1s steps(1) infinite; }}
@keyframes blink {{ 50% {{ opacity: 0; }} }}
{globe_css}
</style>
<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>
<path d="M0.5 {BAR_H} V10.5 a10 10 0 0 1 10 -10 H{WIDTH - 10.5} a10 10 0 0 1 10 10 V{BAR_H} Z" fill="{t["bar"]}"/>
<line x1="0.5" y1="{BAR_H}" x2="{WIDTH - 0.5}" y2="{BAR_H}" stroke="{t["border"]}"/>
{dots}
<text x="{WIDTH / 2}" y="{BAR_H / 2 + 4}" text-anchor="middle" class="title">barne856@github: ~</text>
<text x="{PAD}" y="{prompt_y}"><tspan class="user">barne856</tspan>@github <tspan class="cwd">~</tspan>&gt; whoami</text>
<rect class="cursor" x="{PAD + len(PROMPT) * CHAR_W}" y="{prompt_y - FONT_SIZE * 0.7:g}" width="{CHAR_W:g}" height="{FONT_SIZE * 0.8:g}" fill="{t["fg"]}"/>
{globe}
{chr(10).join(parts)}
</svg>
"""


def write_cards(vibe: str) -> None:
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    for name in THEMES:
        (out / f"whoami-{name}.svg").write_text(render(vibe, name), encoding="utf-8")
