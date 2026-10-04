import re


BASE_STYLE = """
body { margin: 0; }
section { padding: var(--margin); box-sizing: border-box; font-family: var(--font-body); font-size: var(--size-body); background: var(--ground); color: var(--text); display: flex; flex-direction: column; gap: var(--gap); }
h1, h2, h3 { font-family: var(--font-display); margin: 0; }
h1, h2 { font-size: var(--size-title); }
h3 { font-size: 30px; }
p { margin: 0; }
.card { padding: 28px; background: var(--surface); border-radius: var(--radius); display: flex; flex-direction: column; gap: 12px; }
.row { display: flex; gap: 32px; }
.row > .card { flex: 1; }
"""


BALLAST = '<svg aria-hidden="true" width="1400" height="560" style="flex: 0 1 560px; min-height: 0; width: 100%"></svg>'


def fill_sections(html: str) -> str:
    def filled(match):
        block = match.group(0)
        has_text = bool(re.sub(r"<[^>]*>|\s+", "", re.sub(r"<(style|script)\b.*?</\1>", "", block, flags=re.S)))
        if "data-chart" in block or BALLAST in block or not has_text:
            return block
        marker = '<aside class="notes"' if '<aside class="notes"' in block else "</section>"
        return block.replace(marker, BALLAST + marker, 1)

    return re.sub(r"<section\b.*?</section>", filled, html, flags=re.S)


def section_markup(content: str | tuple[str, str], ballast: str = "") -> str:
    attributes, markup = ("", content) if isinstance(content, str) else content
    return f'<section{attributes}>{markup}{ballast}<aside class="notes">notes</aside></section>'


def deck(sections: list, style: str = "", filled: bool = False) -> str:
    body = "\n".join(section_markup(content, BALLAST if filled and "data-chart" not in str(content) else "") for content in sections)
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Gate fixture</title><style>{BASE_STYLE}{style}</style></head><body>\n{body}\n</body></html>\n'


HEADING = "<h2>Revenue grew 18 percent in the third quarter</h2>"
BODY = "<p>The logistics business closed the quarter above its plan in every region.</p>"

SEEDED_STYLE = """
.short { height: 700px; }
.callout { border-left: 10px solid var(--accent); padding: 24px 28px; background: var(--surface); }
.strip { position: relative; padding: 28px 40px; background: var(--surface); }
.strip > i.bar { position: absolute; left: 0; top: 0; width: 8px; height: 100%; background: var(--accent); }
.round { padding: 40px; border-radius: 48px; background: var(--surface); }
.eyebrow { font-size: 20px; letter-spacing: 0.1em; color: var(--accent); }
.tile { width: 72px; height: 72px; border-radius: 16px; background: var(--surface); display: flex; align-items: center; justify-content: center; font-size: 40px; }
.outer { padding: 40px; background: var(--surface); border-radius: var(--radius); }
.inner { padding: 24px; background: var(--ground); border-radius: var(--radius); }
.gradient-text { background: linear-gradient(90deg, #1F5FBF, #0F766E); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; color: transparent; }
.glass { padding: 40px; backdrop-filter: blur(14px); background: rgba(255, 255, 255, 0.4); border-radius: var(--radius); }
.grid-background { background-image: linear-gradient(rgba(20, 33, 61, 0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(20, 33, 61, 0.1) 1px, transparent 1px); background-size: 40px 40px; }
.stripes { background-image: repeating-linear-gradient(45deg, rgba(20, 33, 61, 0.08) 0 12px, transparent 12px 24px); }
.halo { width: 900px; height: 500px; background: radial-gradient(circle at 50% 50%, rgba(31, 95, 191, 0.35), transparent 70%); }
.glow { padding: 40px; border-radius: var(--radius); background: var(--ground); box-shadow: 0 0 48px rgba(31, 95, 191, 0.6); }
.hairline-shadow { padding: 40px; border: 1px solid var(--line); border-radius: var(--radius); box-shadow: 0 24px 64px rgba(0, 0, 0, 0.18); }
.tight { letter-spacing: -0.06em; }
.oversized { font-size: 148px; line-height: 1.05; }
.flat { font-size: 26px; }
.cream { background: #F6EFDD; }
.purple-blue { padding: 40px; background: linear-gradient(90deg, #7C3AED, #2563EB); color: #FFFFFF; border-radius: var(--radius); }
"""

SEEDED = {
    "CANVAS_NOT_FILLED": (' class="short"', f'{HEADING}{BODY}'),
    "ONE_SIDED_ACCENT_BAR": f'{HEADING}<div class="callout">{BODY}</div>',
    "EXTREME_RADIUS": f'{HEADING}<div class="round">{BODY}</div>',
    "LABEL_ABOVE_HEADING": f'<p class="eyebrow">QUARTERLY REVIEW</p>{HEADING}{BODY}',
    "ICON_ABOVE_HEADING": f'<div class="tile"><i data-icon="rocket"></i></div><h3>Faster delivery</h3>{BODY}',
    "IDENTICAL_CARD_GRID": f'{HEADING}<div class="row"><div class="card"><h3>Speed</h3><p>Orders ship in one day.</p></div><div class="card"><h3>Cost</h3><p>Freight cost fell by six percent.</p></div><div class="card"><h3>Quality</h3><p>Damage claims halved this year.</p></div></div>',
    "NESTED_CARD": f'{HEADING}<div class="outer"><div class="inner">{BODY}</div></div>',
    "GRADIENT_TEXT": f'<h2 class="gradient-text">Revenue grew 18 percent in the third quarter</h2>{BODY}',
    "GLASS_BLUR": f'{HEADING}<div class="glass">{BODY}</div>',
    "GRID_STRIPE_BACKGROUND": f'<div class="grid-background" style="padding:40px">{HEADING}{BODY}</div>',
    "RADIAL_HALO": f'{HEADING}<div class="halo">{BODY}</div>',
    "GLOW_SHADOW": f'{HEADING}<div class="glow">{BODY}</div>',
    "HAIRLINE_WIDE_SHADOW": f'{HEADING}<div class="hairline-shadow">{BODY}</div>',
    "TIGHT_TRACKING": f'<h2 class="tight">Revenue grew 18 percent in the third quarter</h2>{BODY}',
    "OVERSIZED_TITLE": f'<h1 class="oversized">Revenue grew 18 percent</h1>{BODY}',
    "FLAT_HIERARCHY": f'<h2 class="flat">Revenue grew 18 percent in the third quarter</h2>{BODY}{BODY}',
    "CREAM_GROUND": f'<div class="cream" style="padding:40px; flex:1">{HEADING}{BODY}</div>',
    "AI_PALETTE": f'{HEADING}<div class="purple-blue">{BODY}</div>',
    "EM_DASH_OVERUSE": f'{HEADING}<p>Revenue grew — in every region — and costs fell — which lifted margin — to a record.</p>',
}

CLEAN_STYLE = """
.centered { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 24px; }
.split { display: flex; gap: 64px; align-items: stretch; flex: 1; }
.split > * { flex: 1; }
.split > p, .split > div { align-self: center; }
.big { font-size: 160px; font-family: var(--font-display); color: var(--accent); line-height: 1; }
table { border-collapse: collapse; width: 100%; font-size: 28px; height: 560px; }
th, td { text-align: left; padding: 14px 0; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-weight: 600; }
.steps { display: flex; flex-direction: column; justify-content: space-between; flex: 1; list-style: none; padding: 0; margin: 0; }
.steps li { display: flex; flex: 1; gap: 24px; align-items: center; border-bottom: 1px solid var(--line); font-size: 30px; }
.steps b { width: 220px; color: var(--accent); }
.wide { flex: 2; }
.narrow { flex: 1; }
.dark { background: var(--text); color: var(--ground); }
.dark h2 { color: var(--ground); }
figure { width: 900px; height: 620px; margin: 0; }
.stretch { flex: 1; align-items: stretch; }
.stretch > .card { justify-content: center; }
"""

CLEAN = [
    [
        f'<div class="centered"><h1>Third quarter results beat the plan</h1>{BODY}</div>',
        f'{HEADING}<div class="split"><figure data-chart="bar" data-labels="Q1, Q2, Q3, Q4 plan" data-values="96, 110, 128, 140" data-unit="M"></figure><p>Q3 was the strongest quarter of the year, ahead of Q2 by 16 percent.</p></div>',
        f'<h2>Regional results</h2><table><tr><th>Region</th><th>Revenue</th><th>Plan</th></tr><tr><td>Seoul</td><td>52M</td><td>48M</td></tr><tr><td>Busan</td><td>41M</td><td>40M</td></tr><tr><td>Daegu</td><td>35M</td><td>33M</td></tr></table>',
        '<h2>Four steps for the fourth quarter</h2><ol class="steps"><li><b>October</b><span>Open the Incheon depot</span></li><li><b>November</b><span>Move peak routes to night shifts</span></li><li><b>December</b><span>Review cost per parcel with the board</span></li><li><b>January</b><span>Publish the new route map</span></li></ol>',
    ],
    [
        '<div class="centered"><h1>Cold chain readiness review</h1><p>Prepared for the operations committee</p></div>',
        '<div class="split"><div class="wide"><h2>Spoilage fell to 0.8 percent</h2><p>Sensors on all 41 trucks report every minute, and alerts reach the dispatcher in under two.</p></div><div class="narrow"><div class="big">0.8%</div><p>spoilage, down from 2.1%</p></div></div>',
        '<h2>Where the losses came from</h2><div class="row stretch"><div class="card" style="flex:2"><h3>Door openings</h3><p>Most losses followed long loading stops at two depots, which now have a second dock door and a fixed stop limit.</p></div><div class="card"><h3>Power cuts</h3><p>Two events, both covered by backup units.</p></div></div>',
    ],
    [
        '<div class="centered"><h1>Hiring plan for the next two quarters</h1></div>',
        '<h2>Headcount by team</h2><div class="split"><figure data-chart="bar" data-labels="Operations, Sales, Support, Data" data-values="12, 8, 6, 4" data-unit=""></figure><p>Operations carries half of the plan because the new depot opens in October.</p></div>',
        '<h2>Costs and timing</h2><table><tr><th>Team</th><th>Start</th><th>Cost</th></tr><tr><td>Operations</td><td>October</td><td>$480k</td></tr><tr><td>Sales</td><td>January</td><td>$320k</td></tr></table>',
    ],
]

VARIANT_STYLE = SEEDED_STYLE + """
.topbar { border-top: 8px solid var(--accent); padding: 28px; background: var(--surface); }
.pill { display: inline-block; align-self: flex-start; padding: 6px 16px; border-radius: 999px; background: var(--accent); color: var(--on-accent); font-size: 20px; }
.number { font-size: 20px; color: var(--accent); }
.plain-icon { font-size: 44px; }
.wide-pill { padding: 28px 64px; border-radius: 999px; background: var(--surface); }
.night { background: #0B1220; color: #22D3EE; padding: 40px; }
.hero-halo { flex: 1; background: radial-gradient(circle at 30% 40%, rgba(31, 95, 191, 0.4), transparent 60%); padding: 40px; }
.cream-section { background: #F7F1E3; }
.glow-text { text-shadow: 0 0 28px rgba(31, 95, 191, 0.9); }
.tight-pixels { letter-spacing: -3px; }
.quad { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.quad > .card { height: 150px; }
"""

SEEDED_VARIANTS = [
    ("ONE_SIDED_ACCENT_BAR", f'{HEADING}<div class="topbar">{BODY}</div>'),
    ("ONE_SIDED_ACCENT_BAR", f'{HEADING}<div class="strip"><i class="bar"></i>{BODY}</div>'),
    ("LABEL_ABOVE_HEADING", f'<span class="pill">NEW</span>{HEADING}{BODY}'),
    ("LABEL_ABOVE_HEADING", f'<div class="card"><span class="number">01</span><h3>Plan the depot</h3><p>Choose the site and the shifts.</p></div>'),
    ("ICON_ABOVE_HEADING", f'<i class="plain-icon" data-icon="truck"></i><h3>Faster delivery</h3>{BODY}'),
    ("EXTREME_RADIUS", f'{HEADING}<div class="wide-pill">{BODY}</div>'),
    ("AI_PALETTE", f'<div class="night"><h2>Revenue grew 18 percent in the third quarter</h2>{BODY}</div>'),
    ("RADIAL_HALO", f'{HEADING}<div class="hero-halo">{BODY}</div>'),
    ("GRID_STRIPE_BACKGROUND", f'<div class="stripes" style="padding:40px">{HEADING}{BODY}</div>'),
    ("IDENTICAL_CARD_GRID", f'{HEADING}<div class="quad"><div class="card"><h3>Speed</h3><p>One day.</p></div><div class="card"><h3>Cost</h3><p>Down six percent.</p></div><div class="card"><h3>Quality</h3><p>Claims halved.</p></div><div class="card"><h3>Reach</h3><p>Nine new cities.</p></div></div>'),
    ("GLOW_SHADOW", f'<h2 class="glow-text">Revenue grew 18 percent in the third quarter</h2>{BODY}'),
    ("CREAM_GROUND", (' class="cream-section"', f'{HEADING}{BODY}')),
    ("TIGHT_TRACKING", f'<h2 class="tight-pixels">Revenue grew 18 percent in the third quarter</h2>{BODY}'),
]
