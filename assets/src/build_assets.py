#!/usr/bin/env python3
"""Build the README artwork (assets/*.svg) for odoo-migrate-to-20.

Visual world: a 1970s pocket timetable. Goldenrod bed, carbon and slate panes raked 11 degrees with
flat baselines, bible-ivory prose panes, vermilion only for stops/faults, bottle green only for
arrived/pass. Text is outlined to paths (GitHub renders SVG as an image, so web fonts cannot load).

Fonts (SIL Open Font License, not redistributed here):
  League Gothic      https://github.com/google/fonts/tree/main/ofl/leaguegothic
  Barlow Condensed   https://github.com/google/fonts/tree/main/ofl/barlowcondensed
Put the .ttf files in assets/src/fonts/ (or pass --fonts DIR) and run:
  python3 assets/src/build_assets.py            # needs: pip install fonttools
"""
import argparse
import math
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
RAKE = math.tan(math.radians(11))

THEMES = {
    "light": dict(bed="#E3A51C", rule="#C98F12", ink="#1B1D1F", slate="#2C3945", ivory="#F1ECDC",
                  pane_text="#1B1D1F", board="#1B1D1F", board_text="#F1ECDC", board_dim="#BDB7A6",
                  head="#E3A51C", green="#1D5E3A", green_text="#F1ECDC", verm="#C8321F", plate="#F1ECDC",
                  plate_text="#1B1D1F", ruler="#F7F3E6", ruler_ink="#1B1D1F", title="#1B1D1F", sub="#1B1D1F"),
    "dark": dict(bed="#16181B", rule="#23272C", ink="#F1ECDC", slate="#2C3945", ivory="#2C3945",
                 pane_text="#F1ECDC", board="#E3A51C", board_text="#1B1D1F", board_dim="#3E3212",
                 head="#1B1D1F", green="#1D5E3A", green_text="#F1ECDC", verm="#C8321F", plate="#1B1D1F",
                 plate_text="#F1ECDC", ruler="#F7F3E6", ruler_ink="#1B1D1F", title="#E3A51C", sub="#F1ECDC"),
}


class Face:
    def __init__(self, path):
        self.font = TTFont(path)
        self.gs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upm = self.font["head"].unitsPerEm
        self.hmtx = self.font["hmtx"]
        os2 = self.font["OS/2"]
        self.cap = getattr(os2, "sCapHeight", 0) or int(self.upm * 0.7)

    def width(self, text, size, track=0.0):
        s = size / self.upm
        w = sum(self.hmtx[self.cmap.get(ord(c), self.cmap.get(32))][0] for c in text) * s
        return w + track * size * max(len(text) - 1, 0)

    def path(self, text, size, x, y, fill, anchor="start", track=0.0, opacity=None):
        """y is the baseline. Returns one <path> for the whole string."""
        s = size / self.upm
        w = self.width(text, size, track)
        x0 = {"start": x, "middle": x - w / 2, "end": x - w}[anchor]
        pen = SVGPathPen(self.gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        cx = 0.0
        for ch in text:
            g = self.cmap.get(ord(ch))
            if g is None:
                g = self.cmap.get(32)
            tp = TransformPen(pen, (s, 0, 0, -s, x0 + cx, y))
            self.gs[g].draw(tp)
            cx += self.hmtx[g][0] * s + track * size
        d = pen.getCommands()
        op = f' fill-opacity="{opacity}"' if opacity is not None else ""
        return f'<path d="{d}" fill="{fill}"{op}/>' if d else ""

    def cap_height(self, size):
        return self.cap * size / self.upm


def rake_poly(x, y, w, h, fill, extra=""):
    """Parallelogram leaning right at the top (11 degrees); x,y is the top-left corner."""
    d = h * RAKE
    pts = f"{x + d:.1f},{y:.1f} {x + w + d:.1f},{y:.1f} {x + w:.1f},{y + h:.1f} {x:.1f},{y + h:.1f}"
    return f'<polygon points="{pts}" fill="{fill}" {extra}/>'


def arrow(x, y, w, color, stroke=3):
    """Horizontal drawn arrow (no glyphs as icons)."""
    return (f'<path d="M{x},{y} H{x + w - 10}" stroke="{color}" stroke-width="{stroke}" fill="none"/>'
            f'<path d="M{x + w - 14},{y - 7} L{x + w},{y} L{x + w - 14},{y + 7} Z" fill="{color}"/>')


def svg(w, h, body, title, desc):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-labelledby="t d"><title id="t">{title}</title><desc id="d">{desc}</desc>{body}</svg>\n')


def bed(w, h, t, step=28):
    rules = "".join(f'<path d="M0,{y} H{w}" stroke="{t["rule"]}" stroke-width="1" opacity="0.55"/>'
                    for y in range(step, h, step))
    cols = "".join(f'<path d="M{x},0 V{h}" stroke="{t["rule"]}" stroke-width="1" opacity="0.28"/>'
                   for x in range(112, w, 112))
    return f'<rect width="{w}" height="{h}" fill="{t["bed"]}"/>{rules}{cols}'


# ----------------------------------------------------------------------------------------- banner
def banner(F, t):
    W, H = 1280, 640
    lg, bs, bm, bb = F["lg"], F["bs"], F["bm"], F["bb"]
    out = [bed(W, H, t)]

    # rail: three numbered plates, the sequence the product runs
    rail_y = 44
    out.append(f'<path d="M48,{rail_y} H1232" stroke="{t["ink"]}" stroke-width="2"/>')
    for i, (num, word, color) in enumerate([("01", "SCAN", t["ink"]), ("02", "FIX", t["ink"]), ("03", "PROVE", t["green"])]):
        x = 48 + i * 400
        light = t is THEMES["light"]
        pfill = color if (light or color == t["green"]) else "#E3A51C"
        ptext = "#F1ECDC" if (light or color == t["green"]) else "#1B1D1F"
        out.append(f'<rect x="{x}" y="{rail_y - 17}" width="42" height="34" fill="{pfill}"/>')
        out.append(bb.path(num, 26, x + 21, rail_y + 9, ptext, anchor="middle"))
        out.append(f'<rect x="{x + 50}" y="{rail_y - 15}" width="{bs.width(word, 24, 0.08) + 16}" height="30" fill="{t["bed"]}"/>')
        out.append(bs.path(word, 24, x + 58, rail_y + 9, t["ink"], track=0.08))

    # headline: flat baselines, one voice
    size = 132
    lines = ["EVERY MODULE", "ARRIVES ON", "ODOO 20."]
    y = 190
    for ln in lines:
        out.append(lg.path(ln, size, 44, y, t["title"], track=0.005))
        y += int(size * 0.86)
    # pitch pane (raked, text flat)
    pane_y, pane_h = y - 64, 104
    out.append(rake_poly(40, pane_y, 560, pane_h, t["ivory"]))
    pitch = ["An agent skill that migrates Odoo 14-19 modules",
             "to Odoo 20, then proves they install and run."]
    for i, ln in enumerate(pitch):
        out.append(bm.path(ln, 27, 66, pane_y + 42 + i * 34, t["pane_text"]))

    # departures board (raked slate of glass)
    bx, by, bw, bh = 606, 92, 566, 462
    out.append('<defs><filter id="soft" x="-10%" y="-10%" width="130%" height="130%"><feGaussianBlur stdDeviation="9"/></filter></defs>')
    out.append(rake_poly(bx, by, bw, bh, "#000000", 'opacity="0.28" filter="url(#soft)" transform="translate(6,12)"'))
    out.append(rake_poly(bx, by, bw, bh, t["board"]))
    lean = lambda yy: (by + bh - yy) * RAKE  # x shift of the rake at height yy
    out.append(lg.path("DEPARTURES", 46, bx + 28 + lean(by + 58), by + 58, t["head"], track=0.02))
    lab = "TO ODOO 20.0"
    lw = bb.width(lab, 22, 0.06) + 22
    lx = bx + bw - 30 - lw + lean(by + 50)
    out.append(f'<rect x="{lx:.1f}" y="{by + 26}" width="{lw:.1f}" height="34" fill="{t["green"]}"/>')
    out.append(bb.path(lab, 22, lx + 11, by + 51, t["green_text"], track=0.06))
    # column heads
    cols = [("FROM", 0), ("MODULE", 86), ("VIA", 272), ("STATUS", 386)]
    hy = by + 104
    for name, cx in cols:
        out.append(bs.path(name, 18, bx + 34 + cx + lean(hy), hy, t["board_dim"], track=0.12))
    out.append(f'<path d="M{bx + 30 + lean(hy + 12):.1f},{hy + 12} H{bx + bw - 26 + lean(hy + 12):.1f}" stroke="{t["board_dim"]}" stroke-width="1"/>')
    rows = [
        ("14.0", "ANY MODULE", "8 STOPS", "SCHEDULED", None),
        ("15.0", "ANY MODULE", "8 STOPS", "SCHEDULED", None),
        ("16.0", "RENAMED FORK", "REBASED", "12/12 TESTS", "arr"),
        ("17.0", "ANY MODULE", "8 STOPS", "SCHEDULED", None),
        ("18.0", "WEBSITE + OWL", "104 > 0", "INSTALLED", "arr"),
        ("19.0", "ANY MODULE", "8 STOPS", "SCHEDULED", None),
    ]
    ry = hy + 52
    for frm, mod, via, status, kind in rows:
        sx = bx + 34 + lean(ry)
        # version plate
        pw = 60
        pfill = t["green"] if kind else t["plate"] if t is THEMES["light"] else "#1B1D1F"
        ptxt = t["green_text"] if kind else ("#1B1D1F" if t is THEMES["light"] else "#E3A51C")
        out.append(f'<rect x="{sx:.1f}" y="{ry - 28}" width="{pw}" height="36" fill="{pfill}"/>')
        out.append(bb.path(frm, 26, sx + pw / 2, ry, ptxt, anchor="middle"))
        out.append(lg.path(mod, 32, sx + 86, ry + 1, t["board_text"], track=0.02))
        if via == "104 > 0":
            vx = sx + 272
            out.append(lg.path("104", 34, vx, ry + 1, t["board_text"]))
            aw = lg.width("104", 34)
            out.append(arrow(vx + aw + 6, ry - 11, 30, t["board_text"], 2.5))
            out.append(lg.path("0", 34, vx + aw + 42, ry + 1, t["board_text"]))
        else:
            out.append(lg.path(via, 32, sx + 272, ry + 1, t["board_text"], track=0.02))
        scol = ("#3DBE7A" if t is THEMES["light"] else "#0F3F29") if kind else t["board_dim"]
        out.append(bs.path(status, 20, sx + 386, ry - 2, scol, track=0.06))
        ry += 56
    # acetate ruler laid across the board
    rx, ry0, rw, rh, ang = 652, 552, 384, 40, -8
    ticks = []
    for i in range(0, 76):
        tx = 12 + i * 4.8
        tl = 16 if i % 10 == 0 else 10 if i % 5 == 0 else 6
        ticks.append(f'<path d="M{tx:.1f},0 V{tl}" stroke="{t["ruler_ink"]}" stroke-width="1" opacity="0.7"/>')
    nums = "".join(bs.path(str(n), 14, 12 + n * 48 + 3, 30, t["ruler_ink"], opacity=0.75) for n in range(1, 8))
    out.append(f'<g transform="translate({rx},{ry0}) rotate({ang})">'
               f'<rect width="{rw}" height="{rh}" fill="{t["ruler"]}" fill-opacity="0.34" stroke="{t["ruler"]}" stroke-opacity="0.6"/>'
               f'{"".join(ticks)}{nums}<circle cx="{rw - 14}" cy="{rh / 2 + 6}" r="5" fill="none" stroke="{t["ruler_ink"]}" stroke-opacity="0.5" stroke-width="2"/></g>')

    # footer strip: where it runs
    fy = 624
    out.append(f'<path d="M48,{fy - 26} H1232" stroke="{t["ink"]}" stroke-width="2"/>')
    foot = "RUNS IN  CLAUDE CODE  /  CODEX  /  CURSOR  /  ANTIGRAVITY  /  GEMINI CLI  /  COPILOT  /  OPENCODE"
    out.append(bs.path(foot, 20, 48, fy, t["sub"], track=0.09))
    out.append(bs.path("AGENT SKILLS FORMAT", 20, 1232, fy, t["sub"], anchor="end", track=0.09))
    return svg(W, H, "".join(out), "odoo-migrate-to-20: every module arrives on Odoo 20",
               "A timetable-style banner. Headline: Every module arrives on Odoo 20. A departures board lists "
               "Odoo 14.0 to 19.0 modules travelling to Odoo 20.0; two real runs are marked arrived: a 16.0 renamed "
               "fork rebased with 12 of 12 tests passing, and an 18.0 website and Owl module taken from 104 findings "
               "to 0 that installs.")


# ----------------------------------------------------------------------------------------- route
STOPS = [
    ("01", "DOCTOR", "Checks Odoo 20, Python 3.12+, PostgreSQL 16+ and Chrome", "doctor.sh", "READY"),
    ("02", "PREPARE", "Copies the module, detects its version, commits a baseline", "prepare.sh", "BASELINE"),
    ("03", "UPGRADE_CODE", "Runs Odoo's own rewrite scripts one by one, core untouched", "run_upgrade_code.sh", "CORE UNTOUCHED"),
    ("04", "SCAN", "100+ known breaks: silent ones, signatures, xmlids, secrets", "scan.py", "0 BLOCKER / 0 SILENT"),
    ("05", "REWRITE", "Python, views, security, Owl 3, Interactions, per area", "references/", "COMMIT PER AREA"),
    ("06", "INSTALL LOOP", "Throwaway database, repeated until the install is clean", "install_test.sh", "RESULT: CLEAN"),
    ("07", "SMOKE TEST", "Odoo clickbot and website pages in headless Chrome", "smoke_test.py", "NO CONSOLE ERRORS"),
    ("08", "REVIEW + REPORT", "Code review, then MIGRATION_20.md with every decision", "odoo-review", "REPORT"),
]


def route(F, t):
    W = 1280
    row_h, top = 70, 128
    H = top + len(STOPS) * row_h + 132
    lg, bs, bm, bb = F["lg"], F["bs"], F["bm"], F["bb"]
    out = [bed(W, H, t)]
    sub = "EIGHT STOPS FROM YOUR VERSION TO ODOO 20.0. EVERY STOP HAS A GATE."
    out.append(bs.path(sub, 24, 48, 56, t["sub"], track=0.07))
    # column heads
    heads = [("STOP", 120), ("WHAT HAPPENS", 404), ("RUNS", 866), ("GATE", 1040)]
    for name, x in heads:
        out.append(bs.path(name, 17, x, top - 14, t["ink"], track=0.14))
    # the line of stops
    lx = 70
    out.append(f'<path d="M{lx},{top + row_h / 2} V{top + (len(STOPS) - 0.5) * row_h}" stroke="{t["ink"]}" stroke-width="4"/>')
    for i, (num, name, what, runs, gate) in enumerate(STOPS):
        y = top + i * row_h
        cy = y + row_h / 2
        # slide (raked ivory pane) per stop
        out.append(rake_poly(100, y + 8, 1128, row_h - 16, t["ivory"]))
        out.append(f'<circle cx="{lx}" cy="{cy}" r="11" fill="{t["bed"]}" stroke="{t["verm"]}" stroke-width="5"/>')
        # stop plate
        out.append(f'<rect x="120" y="{cy - 17}" width="44" height="34" fill="{t["ink"] if t is THEMES["light"] else "#E3A51C"}"/>')
        out.append(bb.path(num, 24, 142, cy + 9, t["ivory"] if t is THEMES["light"] else "#1B1D1F", anchor="middle"))
        out.append(lg.path(name, 34, 178, cy + 12, t["pane_text"], track=0.02))
        out.append(bm.path(what, 20, 404, cy + 7, t["pane_text"]))
        # runs: slate code plate
        cw = bs.width(runs, 17, 0.02) + 18
        out.append(f'<rect x="866" y="{cy - 15}" width="{cw:.1f}" height="30" fill="{t["slate"] if t is THEMES["light"] else "#16181B"}"/>')
        out.append(bs.path(runs, 17, 875, cy + 6, "#F1ECDC", track=0.02))
        # gate: green check plate
        gw = bs.width(gate, 15, 0.05) + 38
        out.append(f'<rect x="1040" y="{cy - 15}" width="{gw:.1f}" height="30" fill="{t["green"]}"/>')
        out.append(f'<path d="M1049,{cy} l6,6 l11,-12" stroke="#F1ECDC" stroke-width="3" fill="none" stroke-linecap="square"/>')
        out.append(bs.path(gate, 15, 1073, cy + 5, "#F1ECDC", track=0.05))
    # arrival
    ay = top + len(STOPS) * row_h + 44
    out.append(f'<rect x="{lx - 22}" y="{ay - 30}" width="44" height="44" fill="{t["green"]}"/>')
    out.append(f'<path d="M{lx - 10},{ay - 8} l7,7 l13,-14" stroke="#F1ECDC" stroke-width="4" fill="none" stroke-linecap="square"/>')
    out.append(lg.path("ARRIVED ON ODOO 20.0", 46, 110, ay + 10, t["title"], track=0.01))
    note = "SOURCE MODULE AND ODOO CORE NEVER TOUCHED  /  ONE COMMIT PER PHASE  /  NOTHING COMMENTED OUT TO PASS"
    out.append(bs.path(note, 18, 110, ay + 50, t["sub"], track=0.08))
    desc = "The route: " + "; ".join(f"stop {n} {nm.lower()}: {w} ({r}, gate {g.lower()})" for n, nm, w, r, g in STOPS)
    return svg(W, H, "".join(out), "The route: eight stops from your Odoo version to Odoo 20.0", desc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default=str(Path(__file__).with_name("fonts")))
    args = ap.parse_args()
    fd = Path(args.fonts)
    F = {"lg": Face(fd / "LeagueGothic-wdth.ttf"), "bs": Face(fd / "BarlowCondensed-SemiBold.ttf"),
         "bm": Face(fd / "BarlowCondensed-Medium.ttf"), "bb": Face(fd / "BarlowCondensed-Bold.ttf")}
    assets = ROOT / "assets"
    for theme, sfx in (("light", ""), ("dark", "-dark")):
        (assets / f"banner{sfx}.svg").write_text(banner(F, THEMES[theme]))
        (assets / f"route{sfx}.svg").write_text(route(F, THEMES[theme]))
    for f in sorted(assets.glob("*.svg")):
        print(f"{f.relative_to(ROOT)}  {f.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
