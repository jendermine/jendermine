import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

USER = os.environ.get("GH_USER", "jendermine")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "assets")

QUERY = """query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar {
  weeks { contributionDays { date contributionCount contributionLevel } } } } } }"""

THEMES = {
    "light": dict(levels=["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"], ink="#1f2328", muted="#59636e",
                  accent="#1a7f37", panel="#ffffff", panel_edge="#d1d9e0"),
    "dark": dict(levels=["#151b23", "#0e4429", "#006d32", "#26a641", "#39d353"], ink="#f0f6fc", muted="#9198a1",
                 accent="#3fb950", panel="#0d1117", panel_edge="#3d444d"),
}
LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        weeks = json.load(resp)["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [[(dt.date.fromisoformat(d["date"]), d["contributionCount"], LEVEL[d["contributionLevel"]]) for d in w["contributionDays"]]
            for w in weeks]


def streaks(days):
    longest, run, start, best = 0, 0, None, (None, None)
    for date, count, _ in days:
        if count:
            run, start = run + 1, start if run else date
            if run > longest:
                longest, best = run, (start, date)
        else:
            run = 0
    current, end = 0, None
    for date, count, _ in reversed(days):
        if count:
            current, end = current + 1, end or date
        elif current or date != days[-1][0]:
            break
    cur_start = end - dt.timedelta(days=current - 1) if current else None
    return longest, best, current, (cur_start, end)


def fmt(d):
    return f"{d:%b} {d.day}" if d else ""


def span(a, b):
    if not a:
        return "none"
    return f"{fmt(a)}, {a.year} to {fmt(b)}, {b.year}" if a.year != b.year else f"{fmt(a)} to {fmt(b)}"


def poly(points, fill):
    return f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in points)}" fill="{fill}"/>'


def shade(hex_colour, factor):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * factor))) for c in (r, g, b))


def render(weeks, t):
    days = [d for w in weeks for d in w]
    total = sum(c for _, c, _ in days)
    best_date, best = max(((d, c) for d, c, _ in days), key=lambda x: x[1])
    longest, longest_span, current, current_span = streaks(days)
    average = total / len(days)

    S, cos, sin, H_MAX = 9.0, 0.866, 0.5, 70.0
    peak = max(best, 1)
    u, v = (S * cos, S * sin), (S * cos, -S * sin)
    ox, oy = 24.0, 128.0
    cells = []
    for wi, week in enumerate(weeks):
        for date, count, level in week:
            di = date.weekday() + 1 if date.weekday() < 6 else 0
            cells.append((wi, di, count, level))
    cells.sort(key=lambda c: (c[0] - c[1], c[0]))
    shapes = []
    for wi, di, count, level in cells:
        px, py = ox + wi * u[0] + di * v[0], oy + wi * u[1] + di * v[1]
        h = 2.0 + (count / peak) ** 0.8 * H_MAX if count else 1.5
        top = t["levels"][level]
        p0, p1, p2, p3 = (px, py), (px + u[0], py + u[1]), (px + u[0] + v[0], py + u[1] + v[1]), (px + v[0], py + v[1])
        up = lambda p: (p[0], p[1] - h)
        shapes.append(poly([p0, p1, up(p1), up(p0)], shade(top, 0.78)))
        shapes.append(poly([p1, p2, up(p2), up(p1)], shade(top, 0.9)))
        shapes.append(poly([up(p0), up(p1), up(p2), up(p3)], top))

    W, H = 820, 470

    def stat(x, y, value, label, sub):
        return (f'<text x="{x}" y="{y}" font-size="28" font-weight="600" fill="{t["accent"]}">{value}</text>'
                f'<text x="{x}" y="{y + 22}" font-size="13" font-weight="600" fill="{t["ink"]}">{label}</text>'
                f'<text x="{x}" y="{y + 40}" font-size="12" fill="{t["muted"]}">{sub}</text>')

    def panel(x, y, w, h, title, body):
        return (f'<text x="{x}" y="{y - 12}" font-size="14" font-weight="600" fill="{t["ink"]}">{title}</text>'
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{t["panel"]}" stroke="{t["panel_edge"]}"/>{body}')

    first, last = days[0][0], days[-1][0]
    right = panel(520, 44, 276, 92, "Contributions",
                  stat(538, 82, f"{total:,}", "Total", span(first, last)) + stat(716, 82, best, "Best day", fmt(best_date)))
    right += (f'<text x="796" y="162" font-size="12" text-anchor="end" fill="{t["muted"]}">Average: '
              f'<tspan fill="{t["accent"]}" font-weight="600">{average:.2f}</tspan> per day</text>')
    left = panel(24, 360, 270, 92, "Streaks",
                 stat(42, 398, f"{longest} days", "Longest", span(*longest_span)) + stat(172, 398, f"{current} days", "Current", span(*current_span)))
    label = f"{USER}: {total:,} contributions in the last year, longest streak {longest} days"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{label}">'
            f'<title>{label}</title><g font-family="{FONT}">{"".join(shapes)}{right}{left}</g></svg>\n')


def main():
    weeks = fetch()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        (OUT / f"isometric-{name}.svg").write_text(render(weeks, theme))


if __name__ == "__main__":
    main()
