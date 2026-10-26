#!/usr/bin/env python3
"""Build the animated SVGs used by the profile README (header, stats cards, footer).

Data comes from the GitHub API through the `gh` CLI, so private-repo languages and
contribution counts are included. Re-run any time to refresh the numbers:

    python3 scripts/build_cards.py
"""
import datetime
import json
import math
import random
import subprocess
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

USER = "0xsri"
OUT = Path(__file__).resolve().parent.parent / "assets"

# Figures that the API can't compute (counted from org git history / known facts)
AUTHORED_COMMITS = "270+"
PRODUCTS = "30+"
ENGINEERS = "25+"
LIVE_APPS = "3"

FONT = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Ubuntu, Arial, sans-serif"
VIOLET, VIOLET_LIGHT, ORANGE, TEXT, MUTED = "#7C3AED", "#A78BFA", "#F97316", "#E5E7EB", "#A1A1AA"

LANG_COLORS = {
    "TypeScript": "#3178C6", "JavaScript": "#F1E05A", "HTML": "#E34C26", "CSS": "#663399",
    "Python": "#3572A5", "PLpgSQL": "#336790", "Shell": "#89E051", "Solidity": "#AA6746",
    "Rust": "#DEA584", "Kotlin": "#A97BFF", "Go": "#00ADD8", "C++": "#F34B7D",
    "Swift": "#F05138", "Dockerfile": "#384D54",
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

    repos = json.loads(gh("repo", "list", USER, "--limit", "200", "--source",
                          "--json", "name,isFork"))
    langs = Counter()
    counted = 0
    for r in repos:
        if r["name"] == USER:
            continue
        data = json.loads(gh("api", f"repos/{USER}/{r['name']}/languages"))
        if data:
            counted += 1
            langs.update(data)

    return {
        "total": sum(days[d] for d in dates),
        "first": first,
        "active_days": sum(1 for d in dates if days[d] > 0),
        "longest": longest,
        "longest_range": best,
        "prs": user["pullRequests"]["totalCount"],
        "contributed_to": user["repositoriesContributedTo"]["totalCount"],
        "orgs": user["organizations"]["totalCount"],
        "repos": counted,
        "langs": langs,
    }


# ---------------------------------------------------------------- helpers

def fmt_date(iso, year=True):
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%b %-d, %Y" if year else "%b %-d")


def anim(delay, rise=10):
    t = f'begin="{delay:.2f}s" dur=".8s" fill="freeze"'
    return (f'<animate attributeName="opacity" from="0" to="1" {t}/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 {rise}" to="0 0" {t} '
            f'calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>')


def up(delay, inner, rise=10):
    """Fade + rise in with SMIL (works for SVGs shown as <img>, unlike CSS fill-mode tricks)."""
    t = f'begin="{delay:.2f}s" dur=".8s" fill="freeze"'
    return (f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" {t}/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 {rise}" to="0 0" {t} '
            f'calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>{inner}</g>')


def svg(w, h, body, style=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'fill="none" role="img">\n<style>\n'
            f'text {{ font-family: {FONT}; }}\n'
            f'{style}</style>\n{body}\n</svg>\n')


def card_frame(w, h, title=None, subtitle=None):
    out = [f'''<defs>
  <linearGradient id="cardBg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#120B2E"/><stop offset="1" stop-color="#1C1240"/>
  </linearGradient>
  <linearGradient id="edge" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{VIOLET}"/><stop offset="1" stop-color="{ORANGE}"/>
  </linearGradient>
</defs>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="14" fill="url(#cardBg)" stroke="#3B2A6B"/>
<rect x="0.5" y="0.5" width="{w-1}" height="3" rx="1.5" fill="url(#edge)" opacity=".9"/>''']
    if title:
        out.append(up(0, f'<text x="26" y="40" font-size="19" font-weight="700" fill="#C4B5FD">{escape(title)}</text>'))
    if subtitle:
        out.append(f'{up(.1, f'<text x="26" y="60" font-size="12" fill="{MUTED}">{escape(subtitle)}</text>')}')
    return "\n".join(out)


def ring(cx, cy, r, frac, big, small, delay=0.2, grad="ringGrad", width=9):
    c = 2 * math.pi * r
    off = c * (1 - frac)
    return f'''<defs><linearGradient id="{grad}" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="{VIOLET_LIGHT}"/><stop offset="1" stop-color="{ORANGE}"/></linearGradient></defs>
<circle cx="{cx}" cy="{cy}" r="{r}" stroke="#2E2357" stroke-width="{width}"/>
<circle cx="{cx}" cy="{cy}" r="{r}" stroke="url(#{grad})" stroke-width="{width}" stroke-linecap="round"
  stroke-dasharray="{c:.1f}" stroke-dashoffset="{off:.1f}" transform="rotate(-90 {cx} {cy})">
  <animate attributeName="stroke-dashoffset" from="{c:.1f}" to="{off:.1f}" dur="1.6s" begin="{delay}s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>
</circle>
{up(delay+.3, f'<text x="{cx}" y="{cy+(4 if small else 10)}" text-anchor="middle" font-size="{30 if small else 34}" font-weight="800" fill="#FFFFFF">{escape(big)}</text>')}
''' + (f'{up(delay+.4, f'<text x="{cx}" y="{cy+22}" text-anchor="middle" font-size="11" font-weight="600" fill="{MUTED}">{escape(small)}</text>')}' if small else "")


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
    body = [card_frame(w, h, "Sri Pardhiv's Engineering Stats")]
    for i, (label, value) in enumerate(rows):
        y = 84 + i * 26
        body.append(f'''<g opacity="0">{anim(.15 + i*.12)}
  <rect x="30" y="{y-11}" width="12" height="12" rx="3.5" fill="url(#edge)"/>
  <text x="52" y="{y}" font-size="14" font-weight="600" fill="{TEXT}">{escape(label)}:</text>
  <text x="285" y="{y}" font-size="14" font-weight="700" fill="#FFFFFF">{escape(value)}</text>
</g>''')
    body.append(ring(408, 118, 50, 0.92, PRODUCTS, "PRODUCTS"))
    return svg(w, h, "\n".join(body))


def languages_card(d):
    w, h = 400, 210
    total = sum(d["langs"].values())
    top = [(k, v / total) for k, v in d["langs"].most_common() if v / total >= 0.001][:10]
    shown = sum(p for _, p in top)
    body = [card_frame(w, h, "Most Used Languages", f"by code volume across {d['repos']} repositories")]
    x, bar_w = 26, w - 52
    body.append(f'''<defs><clipPath id="barClip"><rect x="26" y="76" width="{bar_w}" height="10" rx="5">
  <animate attributeName="width" from="0" to="{bar_w}" dur="1.4s" begin=".3s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>
</rect></clipPath></defs>
<rect x="26" y="76" width="{bar_w}" height="10" rx="5" fill="#2E2357"/>
<g clip-path="url(#barClip)">''')
    for name, p in top:
        seg = bar_w * p / shown
        body.append(f'<rect x="{x:.2f}" y="76" width="{seg + .5:.2f}" height="10" fill="{LANG_COLORS.get(name, "#8B8B8B")}"/>')
        x += seg
    body.append("</g>")
    for i, (name, p) in enumerate(top):
        col, row = i % 2, i // 2
        lx, ly = 30 + col * 185, 112 + row * 20
        label = "PL/pgSQL" if name == "PLpgSQL" else name
        body.append(f'''<g opacity="0">{anim(.5 + i*.07)}
  <circle cx="{lx}" cy="{ly-4}" r="5" fill="{LANG_COLORS.get(name, "#8B8B8B")}"/>
  <text x="{lx+12}" y="{ly}" font-size="12.5" fill="{TEXT}">{escape(label)} <tspan fill="{MUTED}">{p*100:.2f}%</tspan></text>
</g>''')
    return svg(w, h, "\n".join(body))


def streak_card(d):
    w, h = 900, 200
    a, b = d["longest_range"]
    same_year = a[:4] == b[:4]
    cols = [
        (150, f"{d['total']:,}", "Total Contributions", f"{fmt_date(d['first'])} – Present"),
        (450, None, "Active Days", "days with contributions"),
        (750, f"{d['longest']} days", "Longest Streak", f"{fmt_date(a, not same_year)} – {fmt_date(b)}"),
    ]
    body = [card_frame(w, h)]
    body.append(f'<line x1="300" y1="40" x2="300" y2="160" stroke="#3B2A6B"/><line x1="600" y1="40" x2="600" y2="160" stroke="#3B2A6B"/>')
    for i, (cx, big, label, sub) in enumerate(cols):
        delay = .2 + i * .2
        if big is None:
            body.append(ring(cx, 82, 44, min(1, d["active_days"] / 150), str(d["active_days"]), None, delay, "streakRing", 7))
            body.append(f'{up(delay+.5, f'<text x="{cx}" y="156" text-anchor="middle" font-size="16" font-weight="700" fill="{ORANGE}">{label}</text>')}')
            body.append(f'{up(delay+.6, f'<text x="{cx}" y="178" text-anchor="middle" font-size="12" fill="{MUTED}">{escape(sub)}</text>')}')
            continue
        body.append(f'''<g opacity="0">{anim(delay)}
  <text x="{cx}" y="96" text-anchor="middle" font-size="40" font-weight="800" fill="{VIOLET_LIGHT}">{escape(big)}</text>
  <text x="{cx}" y="128" text-anchor="middle" font-size="16" font-weight="700" fill="{TEXT}">{escape(label)}</text>
  <text x="{cx}" y="152" text-anchor="middle" font-size="12" fill="{MUTED}">{escape(sub)}</text>
</g>''')
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
    body = [f'''<defs>
  <linearGradient id="tileBg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1C1240"/><stop offset="1" stop-color="#120B2E"/></linearGradient>
  <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FDE68A"/><stop offset=".5" stop-color="#F59E0B"/><stop offset="1" stop-color="#B45309"/></linearGradient>
  <linearGradient id="violet" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#E9D5FF"/><stop offset=".5" stop-color="{VIOLET_LIGHT}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>
  <linearGradient id="shine" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".75"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <linearGradient id="barGrad" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{VIOLET}"/><stop offset="1" stop-color="{ORANGE}"/></linearGradient>
</defs>''']
    cup = ("M-22 0H22V8C22 27 12 37 0 37C-12 37-22 27-22 8Z")
    for i, (title, line1, line2) in enumerate(tiles):
        x = i * (tw + gap)
        cx = x + tw / 2
        fill = "gold" if i % 2 == 0 else "violet"
        delay = .1 + i * .12
        body.append(f'''<g opacity="0">{anim(delay)}
  <rect x="{x+.5}" y=".5" width="{tw-1}" height="{th-1}" rx="12" fill="url(#tileBg)" stroke="#3B2A6B"/>
  <text x="{cx}" y="24" text-anchor="middle" font-size="13" font-weight="800" fill="#FFFFFF">{escape(title)}</text>
  <g transform="translate({cx} 40)">
    <clipPath id="cup{i}"><path d="{cup}"/></clipPath>
    <path d="M-22 5C-36 5-36 25-17 27" stroke="url(#{fill})" stroke-width="4" fill="none"/>
    <path d="M22 5C36 5 36 25 17 27" stroke="url(#{fill})" stroke-width="4" fill="none"/>
    <path d="{cup}" fill="url(#{fill})"/>
    <g clip-path="url(#cup{i})"><rect x="-70" y="-5" width="30" height="50" fill="url(#shine)" transform="skewX(-20)">
      <animate attributeName="x" values="-70;60;60" keyTimes="0;.35;1" dur="3.5s" begin="{1 + i*.25:.2f}s" repeatCount="indefinite"/>
    </rect></g>
    <rect x="-4" y="37" width="8" height="9" fill="url(#{fill})"/>
    <rect x="-16" y="45" width="32" height="7" rx="2" fill="url(#{fill})"/>
    <text x="0" y="24" text-anchor="middle" font-size="18" fill="#FFFFFF" opacity=".95">★</text>
  </g>
  <text x="{cx}" y="118" text-anchor="middle" font-size="13" font-weight="700" fill="{TEXT}">{escape(line1)}</text>
  <text x="{cx}" y="136" text-anchor="middle" font-size="10.5" fill="{MUTED}">{escape(line2)}</text>
  <rect x="{x+16}" y="146" width="{tw-32}" height="4" rx="2" fill="url(#barGrad)"/>
</g>''')
    return svg(w, th, "\n".join(body))


def header():
    w, h = 1200, 360
    rnd = random.Random(7)
    stars = []
    for _ in range(70):
        sx, sy, r = rnd.uniform(0, w), rnd.uniform(0, 250), rnd.uniform(.5, 1.7)
        stars.append(f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{r:.1f}" fill="#fff" class="tw" '
                     f'style="animation-duration:{rnd.uniform(2, 5):.1f}s;animation-delay:{rnd.uniform(0, 4):.1f}s"/>')
    horizon = 270
    verticals = "".join(f'<line x1="{600 + i*26}" y1="{horizon}" x2="{600 + i*190}" y2="{h}"/>' for i in range(-14, 15))
    horizontals = "".join(f'<line x1="0" y1="{horizon + j*15}" x2="{w}" y2="{horizon + j*15}"/>' for j in range(0, 8))
    pills = ["Product Strategy", "System Architecture", "Full-Stack", "Mobile", "Web3", "AI"]
    pw = [len(p) * 8.2 + 30 for p in pills]
    total = sum(pw) + 12 * (len(pills) - 1)
    px = (w - total) / 2
    pill_svg = []
    for i, (p, wd) in enumerate(zip(pills, pw)):
        pill_svg.append(f'''<g opacity="0">{anim(1.1 + i*.12)}
  <rect x="{px:.1f}" y="214" width="{wd:.1f}" height="32" rx="16" fill="#7C3AED" fill-opacity=".18" stroke="{VIOLET_LIGHT}" stroke-opacity=".6"/>
  <text x="{px + wd/2:.1f}" y="235" text-anchor="middle" font-size="14" font-weight="600" fill="#EDE9FE">{escape(p)}</text>
</g>''')
        px += wd + 12
    style = '''
.tw { animation: twinkle 3s ease-in-out infinite alternate; }
@keyframes twinkle { from { opacity: .15; } to { opacity: 1; } }
.b1 { animation: drift1 16s ease-in-out infinite alternate; }
.b2 { animation: drift2 19s ease-in-out infinite alternate; }
.b3 { animation: drift3 23s ease-in-out infinite alternate; }
.b4 { animation: drift4 17s ease-in-out infinite alternate; }
@keyframes drift1 { to { transform: translate(260px, 60px); } }
@keyframes drift2 { to { transform: translate(-300px, 50px); } }
@keyframes drift3 { to { transform: translate(180px, -70px); } }
@keyframes drift4 { to { transform: translate(-200px, -40px); } }
.grid { animation: roll 1.2s linear infinite; }
@keyframes roll { from { transform: translateY(0); } to { transform: translateY(15px); } }
.glow { animation: pulse 3s ease-in-out infinite alternate; }
@keyframes pulse { from { opacity: .45; } to { opacity: 1; } }
'''
    body = f'''<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#05030F"/><stop offset=".6" stop-color="#140A33"/><stop offset="1" stop-color="#22103F"/>
  </linearGradient>
  <filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="55"/></filter>
  <filter id="softGlow" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="10"/></filter>
  <linearGradient id="nameGrad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="1200" y2="0" spreadMethod="repeat">
    <stop offset="0" stop-color="#FFFFFF"/><stop offset=".3" stop-color="#DDD6FE"/>
    <stop offset=".5" stop-color="#FDBA74"/><stop offset=".7" stop-color="#DDD6FE"/><stop offset="1" stop-color="#FFFFFF"/>
    <animateTransform attributeName="gradientTransform" type="translate" from="0 0" to="1200 0" dur="7s" repeatCount="indefinite"/>
  </linearGradient>
  <linearGradient id="horizonLine" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{VIOLET}" stop-opacity="0"/><stop offset=".3" stop-color="{VIOLET_LIGHT}"/>
    <stop offset=".5" stop-color="{ORANGE}"/><stop offset=".7" stop-color="{VIOLET_LIGHT}"/><stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="fadeDown" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity="1"/>
  </linearGradient>
  <mask id="gridMask"><rect x="0" y="{horizon}" width="{w}" height="{h-horizon}" fill="url(#fadeDown)"/></mask>
  <clipPath id="frame"><rect width="{w}" height="{h}" rx="18"/></clipPath>
</defs>
<g clip-path="url(#frame)">
  <rect width="{w}" height="{h}" fill="url(#sky)"/>
  <g filter="url(#blur)">
    <circle class="b1" cx="230" cy="110" r="170" fill="{VIOLET}" opacity=".55"/>
    <circle class="b2" cx="980" cy="90" r="160" fill="{ORANGE}" opacity=".33"/>
    <circle class="b3" cx="620" cy="290" r="190" fill="#22D3EE" opacity=".16"/>
    <circle class="b4" cx="1060" cy="270" r="130" fill="#C026D3" opacity=".35"/>
  </g>
  {"".join(stars)}
  <g mask="url(#gridMask)" stroke="{VIOLET_LIGHT}" stroke-opacity=".45" stroke-width="1">
    {verticals}
    <g class="grid">{horizontals}</g>
  </g>
  <rect class="glow" x="0" y="{horizon-1}" width="{w}" height="2" fill="url(#horizonLine)"/>
  <rect class="glow" x="0" y="{horizon-6}" width="{w}" height="12" fill="url(#horizonLine)" filter="url(#softGlow)" opacity=".8"/>
  <g opacity="0">{anim(.2)}
    <text x="600" y="128" text-anchor="middle" font-size="84" font-weight="800" letter-spacing="-1.5" fill="{VIOLET}" opacity=".75" filter="url(#softGlow)">U Sri Pardhiv</text>
    <text x="600" y="128" text-anchor="middle" font-size="84" font-weight="800" letter-spacing="-1.5" fill="url(#nameGrad)">U Sri Pardhiv</text>
  </g>
  {up(.6, f'<text x="600" y="182" text-anchor="middle" font-size="25" font-weight="600" fill="#E9D5FF">Product &amp; Engineering Leader  ·  Ex-CPO, Exaflair Technologies</text>')}
  {"".join(pill_svg)}
</g>'''
    return svg(w, h, body, style)


def footer():
    w, h = 1200, 140

    def wave(phase, amp, base):
        pts = [f"M0 {h}"]
        for x in range(0, w + 1, 40):
            y = base + amp * math.sin(2 * math.pi * x / w * 1.5 + phase)
            pts.append(f"L{x} {y:.1f}")
        pts.append(f"L{w} {h}Z")
        return " ".join(pts)

    layers = []
    for i, (amp, base, op, dur) in enumerate([(14, 60, .35, 9), (18, 78, .55, 7), (12, 96, 1, 5)]):
        frames = ";".join(wave(p + i, amp, base) for p in (0, math.pi, 2 * math.pi))
        layers.append(f'<path d="{wave(i, amp, base)}" fill="url(#footGrad)" opacity="{op}">'
                      f'<animate attributeName="d" values="{frames}" dur="{dur}s" repeatCount="indefinite"/></path>')
    body = f'''<defs><linearGradient id="footGrad" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{ORANGE}"/><stop offset=".5" stop-color="#6D28D9"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient></defs>
{"".join(layers)}
{up(.5, f'<text x="600" y="128" text-anchor="middle" font-size="15" font-weight="600" fill="#FFFFFF" letter-spacing="3">THANKS FOR VISITING</text>')}'''
    return svg(w, h, body)


def main():
    OUT.mkdir(exist_ok=True)
    d = fetch_data()
    files = {
        "header.svg": header(),
        "footer.svg": footer(),
        "stats.svg": stats_card(d),
        "languages.svg": languages_card(d),
        "streak.svg": streak_card(d),
        "trophies.svg": trophies_card(d),
    }
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
    print(json.dumps({k: v for k, v in d.items() if k != "langs"}, indent=2))
    print("wrote", ", ".join(files))


if __name__ == "__main__":
    main()
