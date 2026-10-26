#!/usr/bin/env python3
"""Build the animated SVGs used by the profile README (header, stats cards, footer).

Contribution data comes from the GitHub API through the `gh` CLI, so private-repo
activity is included. Re-run any time to refresh the numbers:

    python3 scripts/build_cards.py
"""
import datetime
import hashlib
import json
import math
import random
import re
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

USER = "0xsri"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
README = ROOT / "README.md"

# Figures that the API can't compute (counted from org git history / known facts)
AUTHORED_COMMITS = "270+"
PRODUCTS = "30+"
ENGINEERS = "25+"
LIVE_APPS = "3"

# Core languages card: share of focus across the stack
CORE_LANGUAGES = [
    ("TypeScript", 34), ("Python", 25), ("JavaScript", 11),
    ("Solidity", 10), ("Go", 10), ("Rust", 10),
]

FONT = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Ubuntu, Arial, sans-serif"

# Palette: GitHub-dark neutrals with a single muted green accent
CANVAS = "#0D1117"
CARD = "#161B22"
BORDER = "#30363D"
TRACK = "#21262D"
WHITE = "#F0F6FC"
TEXT = "#C9D1D9"
MUTED = "#8B949E"
GREEN = "#2EA043"
GREEN_DARK = "#196C2E"
GREEN_LEVELS = ["#0E4429", "#006D32", "#1F8C3B", "#2EA043"]

LANG_COLORS = {
    "TypeScript": "#2EA043", "Python": "#A3BE8C", "JavaScript": "#E6EDF3",
    "Solidity": "#8B949E", "Go": "#3E7B52", "Rust": "#57606A",
}


# ---------------------------------------------------------------- data

def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def graphql(query):
    return json.loads(gh("api", "graphql", "-f", f"query={query}"))["data"]


def fetch_data():
    user = graphql(f"""query {{ user(login: "{USER}") {{
        contributionsCollection {{ contributionYears }}
        pullRequests {{ totalCount }}
        repositoriesContributedTo(includeUserRepositories: true,
            contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {{ totalCount }}
        organizations(first: 20) {{ totalCount }} }} }}""")["user"]

    days = {}
    for year in user["contributionsCollection"]["contributionYears"]:
        cal = graphql(f"""query {{ user(login: "{USER}") {{
            contributionsCollection(from: "{year}-01-01T00:00:00Z", to: "{year}-12-31T23:59:59Z") {{
              contributionCalendar {{ weeks {{ contributionDays {{ date contributionCount }} }} }} }} }} }}""")
        for week in cal["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                days[d["date"]] = d["contributionCount"]

    today = datetime.date.today().isoformat()
    dates = sorted(d for d in days if d <= today)
    first = next(d for d in dates if days[d] > 0)
    longest, run, run_start, best = 0, 0, None, (first, first)
    for d in dates:
        if days[d] > 0:
            run += 1
            run_start = run_start or d
            if run > longest:
                longest, best = run, (run_start, d)
        else:
            run, run_start = 0, None

    return {
        "total": sum(days[d] for d in dates),
        "first": first,
        "active_days": sum(1 for d in dates if days[d] > 0),
        "longest": longest,
        "longest_range": best,
        "prs": user["pullRequests"]["totalCount"],
        "contributed_to": user["repositoriesContributedTo"]["totalCount"],
        "orgs": user["organizations"]["totalCount"],
    }


# ---------------------------------------------------------------- helpers

def fmt_date(iso, year=True):
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%b %-d, %Y" if year else "%b %-d")


def anim(delay, rise=8):
    """Fade + rise in with SMIL (works for SVGs shown as <img>)."""
    t = f'begin="{delay:.2f}s" dur=".8s" fill="freeze"'
    return (f'<animate attributeName="opacity" from="0" to="1" {t}/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 {rise}" to="0 0" {t} '
            f'calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>')


def up(delay, inner, rise=8):
    return f'<g opacity="0">{anim(delay, rise)}{inner}</g>'


def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'fill="none" role="img">\n<style>text {{ font-family: {FONT}; }}</style>\n{body}\n</svg>\n')


def card_frame(w, h, title=None, subtitle=None):
    out = [f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{CARD}" stroke="{BORDER}"/>']
    if title:
        out.append(up(0, f'<text x="26" y="40" font-size="18" font-weight="600" fill="{WHITE}">{escape(title)}</text>'))
    if subtitle:
        out.append(up(.1, f'<text x="26" y="60" font-size="12" fill="{MUTED}">{escape(subtitle)}</text>'))
    return "\n".join(out)


def ring(cx, cy, r, frac, big, small, delay=0.2, width=8):
    c = 2 * math.pi * r
    off = c * (1 - frac)
    out = f'''<circle cx="{cx}" cy="{cy}" r="{r}" stroke="{TRACK}" stroke-width="{width}"/>
<circle cx="{cx}" cy="{cy}" r="{r}" stroke="{GREEN}" stroke-width="{width}" stroke-linecap="round"
  stroke-dasharray="{c:.1f}" stroke-dashoffset="{off:.1f}" transform="rotate(-90 {cx} {cy})">
  <animate attributeName="stroke-dashoffset" from="{c:.1f}" to="{off:.1f}" dur="1.6s" begin="{delay}s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>
</circle>
'''
    out += up(delay + .3, f'<text x="{cx}" y="{cy + (4 if small else 10)}" text-anchor="middle" font-size="{30 if small else 32}" font-weight="700" fill="{WHITE}">{escape(big)}</text>')
    if small:
        out += up(delay + .4, f'<text x="{cx}" y="{cy + 22}" text-anchor="middle" font-size="10.5" font-weight="600" letter-spacing="1" fill="{MUTED}">{escape(small)}</text>')
    return out


def contribution_grid(x0, y0, cols, rows, size, gap, seed, wave=True):
    """GitHub-style contribution squares with a slow green wave sweeping across."""
    rnd = random.Random(seed)
    out = []
    for c in range(cols):
        for r in range(rows):
            x, y = x0 + c * (size + gap), y0 + r * (size + gap)
            level = rnd.choices([None, 0, 1, 2, 3], weights=[34, 26, 20, 13, 7])[0]
            base = TRACK if level is None else GREEN_LEVELS[level]
            out.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="3" fill="{base}"/>')
            if wave:
                begin = c * .11 + r * .06
                out.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="3" fill="{GREEN}" opacity="0">'
                           f'<animate attributeName="opacity" values="0;.85;0;0" keyTimes="0;.12;.3;1" dur="5s" '
                           f'begin="{begin:.2f}s" repeatCount="indefinite"/></rect>')
    return "\n".join(out)


# ---------------------------------------------------------------- cards

def stats_card(d):
    w, h = 495, 210
    rows = [
        ("Total Contributions", f"{d['total']:,}"),
        ("Commits Authored (org repos)", AUTHORED_COMMITS),
        ("Pull Requests", str(d["prs"])),
        ("Repositories Contributed To", str(d["contributed_to"])),
        ("Organizations", str(d["orgs"])),
    ]
    body = [card_frame(w, h, "Engineering Stats")]
    for i, (label, value) in enumerate(rows):
        y = 84 + i * 26
        body.append(up(.15 + i * .12, f'''
  <rect x="28" y="{y-11}" width="11" height="11" rx="2.5" fill="{GREEN_LEVELS[min(3, 3 - i % 3)]}"/>
  <text x="50" y="{y}" font-size="14" fill="{TEXT}">{escape(label)}</text>
  <text x="290" y="{y}" font-size="14" font-weight="600" fill="{WHITE}">{escape(value)}</text>'''))
    body.append(ring(410, 118, 50, 0.92, PRODUCTS, "PRODUCTS"))
    return svg(w, h, "\n".join(body))


def languages_card():
    w, h = 400, 210
    total = sum(p for _, p in CORE_LANGUAGES)
    body = [card_frame(w, h, "Core Languages", "primary languages across my stack")]
    x, bar_w = 26, w - 52
    body.append(f'''<clipPath id="barClip"><rect x="26" y="78" width="{bar_w}" height="8" rx="4">
  <animate attributeName="width" from="0" to="{bar_w}" dur="1.4s" begin=".3s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>
</rect></clipPath>
<rect x="26" y="78" width="{bar_w}" height="8" rx="4" fill="{TRACK}"/>
<g clip-path="url(#barClip)">''')
    for name, p in CORE_LANGUAGES:
        seg = bar_w * p / total
        body.append(f'<rect x="{x:.2f}" y="78" width="{seg - 2:.2f}" height="8" fill="{LANG_COLORS[name]}"/>')
        x += seg
    body.append("</g>")
    for i, (name, p) in enumerate(CORE_LANGUAGES):
        col, row = i % 2, i // 2
        lx, ly = 30 + col * 185, 120 + row * 28
        body.append(up(.5 + i * .08, f'''
  <circle cx="{lx}" cy="{ly-4.5}" r="5" fill="{LANG_COLORS[name]}"/>
  <text x="{lx+14}" y="{ly}" font-size="14" fill="{TEXT}">{escape(name)} <tspan fill="{MUTED}" dx="4">{p}%</tspan></text>'''))
    return svg(w, h, "\n".join(body))


def streak_card(d):
    w, h = 900, 200
    a, b = d["longest_range"]
    same_year = a[:4] == b[:4]
    body = [card_frame(w, h)]
    body.append(f'<line x1="300" y1="44" x2="300" y2="156" stroke="{BORDER}"/>'
                f'<line x1="600" y1="44" x2="600" y2="156" stroke="{BORDER}"/>')
    for i, (cx, big, label, sub) in enumerate([
        (150, f"{d['total']:,}", "Total Contributions", f"{fmt_date(d['first'])} – Present"),
        (750, f"{d['longest']} days", "Longest Streak", f"{fmt_date(a, not same_year)} – {fmt_date(b)}"),
    ]):
        body.append(up(.2 + i * .4, f'''
  <text x="{cx}" y="96" text-anchor="middle" font-size="38" font-weight="700" fill="{WHITE}">{escape(big)}</text>
  <text x="{cx}" y="128" text-anchor="middle" font-size="15" font-weight="600" fill="{TEXT}">{escape(label)}</text>
  <text x="{cx}" y="152" text-anchor="middle" font-size="12" fill="{MUTED}">{escape(sub)}</text>'''))
    body.append(ring(450, 82, 42, min(1, d["active_days"] / 150), str(d["active_days"]), None, .4, 7))
    body.append(up(.9, f'<text x="450" y="152" text-anchor="middle" font-size="15" font-weight="600" fill="{GREEN}">Active Days</text>'))
    body.append(up(1.0, f'<text x="450" y="174" text-anchor="middle" font-size="12" fill="{MUTED}">days with contributions</text>'))
    return svg(w, h, "\n".join(body))


def trophies_card(d):
    tiles = [
        ("Leadership", "Ex-CPO", "Exaflair Technologies"),
        ("Products", f"{PRODUCTS} Shipped", "Web · Mobile · Chain"),
        ("Team", f"{ENGINEERS} Engineers", "Led across teams"),
        ("Mobile", f"{LIVE_APPS} Apps Live", "App Store · Play"),
        ("Web3", "Solana + EVM", "Contracts shipped"),
        ("Polyglot", "10+ Languages", "TS · Py · Go · C++"),
        ("Builder", f"{d['total']:,}", "Contributions"),
    ]
    tw, th, gap = 124, 160, 8
    w = len(tiles) * tw + (len(tiles) - 1) * gap
    body = ['''<defs>
  <linearGradient id="tileBg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1C1240"/><stop offset="1" stop-color="#120B2E"/></linearGradient>
  <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FDE68A"/><stop offset=".5" stop-color="#F59E0B"/><stop offset="1" stop-color="#B45309"/></linearGradient>
  <linearGradient id="violet" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#E9D5FF"/><stop offset=".5" stop-color="#A78BFA"/><stop offset="1" stop-color="#7C3AED"/></linearGradient>
  <linearGradient id="shine" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".75"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <linearGradient id="barGrad" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#7C3AED"/><stop offset="1" stop-color="#F97316"/></linearGradient>
</defs>''']
    cup = "M-22 0H22V8C22 27 12 37 0 37C-12 37-22 27-22 8Z"
    for i, (title, line1, line2) in enumerate(tiles):
        x = i * (tw + gap)
        cx = x + tw / 2
        cup_fill = "gold" if i % 2 == 0 else "violet"
        body.append(up(.1 + i * .12, f'''
  <rect x="{x+.5}" y=".5" width="{tw-1}" height="{th-1}" rx="12" fill="url(#tileBg)" stroke="#3B2A6B"/>
  <text x="{cx}" y="24" text-anchor="middle" font-size="13" font-weight="800" fill="#FFFFFF">{escape(title)}</text>
  <g transform="translate({cx} 40)">
    <clipPath id="cup{i}"><path d="{cup}"/></clipPath>
    <path d="M-22 5C-36 5-36 25-17 27" stroke="url(#{cup_fill})" stroke-width="4" fill="none"/>
    <path d="M22 5C36 5 36 25 17 27" stroke="url(#{cup_fill})" stroke-width="4" fill="none"/>
    <path d="{cup}" fill="url(#{cup_fill})"/>
    <g clip-path="url(#cup{i})"><rect x="-70" y="-5" width="26" height="50" fill="url(#shine)" transform="skewX(-20)">
      <animate attributeName="x" values="-70;60;60" keyTimes="0;.35;1" dur="4s" begin="{1 + i*.3:.2f}s" repeatCount="indefinite"/>
    </rect></g>
    <rect x="-4" y="37" width="8" height="9" fill="url(#{cup_fill})"/>
    <rect x="-16" y="45" width="32" height="7" rx="2" fill="url(#{cup_fill})"/>
    <text x="0" y="24" text-anchor="middle" font-size="18" fill="#FFFFFF" opacity=".95">★</text>
  </g>
  <text x="{cx}" y="118" text-anchor="middle" font-size="13" font-weight="700" fill="#E5E7EB">{escape(line1)}</text>
  <text x="{cx}" y="136" text-anchor="middle" font-size="10.5" fill="#A1A1AA">{escape(line2)}</text>
  <rect x="{x+16}" y="146" width="{tw-32}" height="4" rx="2" fill="url(#barGrad)"/>'''))
    return svg(w, th, "\n".join(body))


def header():
    w, h = 1200, 290
    pills = ["Product Strategy", "System Architecture", "Full-Stack", "Mobile", "Web3", "AI"]
    px, pill_svg = 72, []
    for i, p in enumerate(pills):
        wd = len(p) * 7.0 + 24
        pill_svg.append(up(1.0 + i * .1, f'''
  <rect x="{px:.1f}" y="226" width="{wd:.1f}" height="30" rx="15" fill="{CARD}" stroke="{BORDER}"/>
  <text x="{px + wd/2:.1f}" y="246" text-anchor="middle" font-size="12.5" font-weight="500" fill="{TEXT}">{escape(p)}</text>'''))
        px += wd + 10
    body = f'''<clipPath id="frame"><rect width="{w}" height="{h}" rx="14"/></clipPath>
<g clip-path="url(#frame)">
  <rect width="{w}" height="{h}" fill="{CANVAS}"/>
  <rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="14" stroke="{BORDER}"/>
  {up(.1, f'<rect x="72" y="66" width="10" height="10" rx="2" fill="{GREEN}"/><text x="92" y="76" font-size="13" font-weight="600" letter-spacing="2.5" fill="{MUTED}">PRODUCT &amp; ENGINEERING LEADER</text>')}
  {up(.25, f'<text x="68" y="146" font-size="68" font-weight="700" letter-spacing="-1.5" fill="{WHITE}">U Sri Pardhiv</text>')}
  {up(.5, f'<text x="72" y="190" font-size="21" fill="{TEXT}">Ex-Chief Product Officer <tspan fill="{MUTED}">·</tspan> Exaflair Technologies</text>')}
  {"".join(pill_svg)}
  <g opacity="0">{anim(.4, 0)}
    {contribution_grid(740, 66, 18, 7, 18, 5, seed=11)}
  </g>
  {up(.8, f'<text x="740" y="248" font-size="11.5" fill="{MUTED}">Less</text>')}
  {up(.8, "".join(f'<rect x="{772 + i*16}" y="238" width="11" height="11" rx="2.5" fill="{c}"/>' for i, c in enumerate([TRACK] + GREEN_LEVELS)))}
  {up(.8, f'<text x="856" y="248" font-size="11.5" fill="{MUTED}">More</text>')}
</g>'''
    return svg(w, h, body)


def footer():
    w, h = 1200, 90
    body = f'''<line x1="0" y1="20" x2="{w}" y2="20" stroke="{BORDER}"/>
<g opacity="0">{anim(.1, 0)}{contribution_grid(489, 36, 12, 1, 14, 5, seed=3)}</g>
{up(.4, f'<text x="600" y="80" text-anchor="middle" font-size="12" font-weight="600" letter-spacing="3" fill="{MUTED}">THANKS FOR VISITING</text>')}'''
    return svg(w, h, body)


def stamp_readme():
    """Version every ./assets link by content hash so browsers never show a stale cached image."""
    def stamp(m):
        path = m.group(1)
        digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()[:8]
        return f'src="./{path}?v={digest}"'
    text = README.read_text(encoding="utf-8")
    README.write_text(re.sub(r'src="\./(assets/[^"?]+)(?:\?v=[0-9a-f]+)?"', stamp, text), encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    d = fetch_data()
    files = {
        "header.svg": header(),
        "footer.svg": footer(),
        "stats.svg": stats_card(d),
        "languages.svg": languages_card(),
        "streak.svg": streak_card(d),
        "trophies.svg": trophies_card(d),
    }
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
    stamp_readme()
    print(json.dumps(d, indent=2))
    print("wrote", ", ".join(files))


if __name__ == "__main__":
    main()
