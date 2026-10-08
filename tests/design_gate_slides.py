BALLAST = '<svg aria-hidden="true" width="1400" height="560" style="flex: 0 1 560px; min-height: 0; width: 100%"></svg>'

HEADING = "<h2>Revenue grew 18 percent in the third quarter</h2>"
BODY = "<p>The logistics business closed the quarter above its plan in every region.</p>"

SEEDED_STYLE = """
.short { height: 700px; }
.callout { border-left: 10px solid var(--accent); padding: 24px 28px; background: var(--surface); }
.strip { position: relative; padding: 28px 40px; background: var(--surface); }
.strip > i.bar { position: absolute; left: 0; top: 0; width: 8px; height: 100%; background: var(--accent); }
.narrow-cell { width: 110px; word-break: break-all; font-size: 28px; }
.spill { position: absolute; left: 1200px; top: 400px; width: 700px; margin: 0; }
.short-card { height: 70px; padding: 28px; background: var(--surface); border-radius: var(--radius); }
.stacked-a { position: absolute; left: 96px; top: 300px; width: 700px; margin: 0; }
.stacked-b { position: absolute; left: 160px; top: 312px; width: 700px; margin: 0; }
.foot { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; padding: 28px; background: var(--surface); border-radius: var(--radius); font-size: 28px; }
.boxed-lower { flex: 1; padding: 28px; background: var(--surface); border-radius: var(--radius); }
"""

FOOT = '<div class="foot"><p>Figures are from the third quarter plan.</p></div>'


UNFOOTED = {"EMPTY_LOWER_BAND", "PAGE_NOT_FILLED"}


def footed(content):
    if isinstance(content, tuple):
        return content[0], content[1] + FOOT
    return content + FOOT

SEEDED = {name: content if name in UNFOOTED else footed(content) for name, content in {
    "CANVAS_NOT_FILLED": (' class="short"', f'{HEADING}{BODY}'),
    "ONE_SIDED_ACCENT_BAR": f'{HEADING}<div class="callout">{BODY}</div>',
    "BROKEN_WORD": f'{HEADING}<div class="narrow-cell">Subscription renews monthly</div>',
    "OUT_OF_FRAME": f'{HEADING}<p class="spill">The logistics business closed the quarter above its plan in every region.</p>',
    "CONTENT_OVERFLOW": f'{HEADING}<div class="short-card"><p>The logistics business closed the quarter above its plan in every region.</p><p>Costs fell in each of the four quarters while volume grew.</p></div>',
    "CONTENT_OVERLAP": f'{HEADING}<p class="stacked-a">The logistics business closed the quarter above its plan in every region.</p><p class="stacked-b">The logistics business closed the quarter above its plan in every region.</p>',
    "EMPTY_LOWER_BAND": f'{HEADING}<div class="boxed-lower">{BODY}</div>',
    "PAGE_NOT_FILLED": f'{HEADING}{BODY}',
    "TEXT_TOO_SMALL": f'{HEADING}<p style="font-size: 16px">The logistics business closed the quarter above its plan in every region.</p>',
    "CHART_COLLAPSED": f'{HEADING}<figure data-chart="bar" data-labels="Q1, Q2" data-values="10, 12" style="width: 600px; height: 120px"></figure>',
}.items()}

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
.split.spread > .narrow { align-self: stretch; display: flex; flex-direction: column; justify-content: center; padding: 48px; background: var(--surface); border-radius: var(--radius); }
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
        '<div class="split spread"><div class="wide"><h2>Spoilage fell to 0.8 percent</h2><p>Sensors on all 41 trucks report every minute, and alerts reach the dispatcher in under two.</p></div><div class="narrow"><div class="big">0.8%</div><p>spoilage, down from 2.1%</p></div></div>',
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
.clipper { height: 40px; overflow: hidden; }
.icon-over { position: absolute; left: 100px; top: 306px; width: 90px; height: 90px; }
.low-column { position: absolute; left: 96px; top: 860px; width: 500px; margin: 0; }
.centered-track { flex: 1; display: flex; flex-direction: column; justify-content: center; }
"""

SEEDED_VARIANTS = [
    ("ONE_SIDED_ACCENT_BAR", f'{HEADING}<div class="topbar">{BODY}</div>'),
    ("ONE_SIDED_ACCENT_BAR", f'{HEADING}<div class="strip"><i class="bar"></i>{BODY}</div>'),
    ("CONTENT_OVERFLOW", f'{HEADING}<div class="clipper"><p>The logistics business closed the quarter above its plan in every region.</p><p>Costs fell in each of the four quarters while volume grew.</p></div>'),
    ("OUT_OF_FRAME", f'{HEADING}<p class="low-column">The logistics business closed the quarter above its plan in every region and beyond.</p>'),
    ("OUT_OF_FRAME", f'{HEADING}<svg class="icon-over" style="left:1540px" aria-hidden="true" width="90" height="90"></svg>{BODY}'),
    ("CONTENT_OVERLAP", f'{HEADING}<svg class="icon-over" aria-hidden="true" width="90" height="90"></svg><p class="stacked-a">The logistics business closed the quarter above its plan in every region.</p>'),
    ("PAGE_NOT_FILLED", f'{HEADING}<div class="centered-track">{BODY}</div>'),
    ("BROKEN_WORD", f'{HEADING}<table style="width: 160px"><tr><td style="word-break: break-all">$19/month</td></tr></table>'),
]
