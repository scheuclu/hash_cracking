"""Render results.csv + project metadata into a self-contained docs/index.html.

Run from the project root:

    uv run python build_site.py

The output is a single HTML file with inline CSS and inline SVG charts — no
external assets, no JS, no build step. Suitable for GitHub Pages served from
the `docs/` directory on `main`.
"""

from __future__ import annotations

import csv
import html
import shlex
from dataclasses import dataclass
from math import log10
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS_CSV = ROOT / "results.csv"
HASH_FILE = ROOT / "hash_inputs.hash"
SOLUTION_FILE = ROOT / "hash_inputs.solution"
OUT = ROOT / "docs" / "index.html"

# Built-in hashcat charset sizes.
HASHCAT_CHARSETS = {"l": 26, "u": 26, "d": 10, "s": 33, "h": 16, "H": 16, "a": 95}

# Headline hardware facts (recorded from the run logs).
GPU_MODEL = "NVIDIA GB10 (Grace Blackwell)"
GPU_PEAK_RATE_MHS = 857  # peak SHA-1 hash rate observed across the sweep
BLOG_URL = "https://www.scheuclu.com/posts/password_hash_crack"
REPO_URL = "https://github.com/scheuclu/hash_cracking"


@dataclass(frozen=True)
class Row:
    desc: str
    args: str
    duration_s: float
    newly_cracked: int
    cumulative_cracked: int
    total_hashes: int
    exit_code: int

    @property
    def cracked_all(self) -> bool:
        return self.cumulative_cracked == self.total_hashes

    @property
    def keyspace(self) -> int:
        return parse_keyspace(self.args)

    @property
    def effective_rate_mhs(self) -> float:
        if self.duration_s <= 0:
            return 0
        return self.keyspace / self.duration_s / 1e6


def parse_keyspace(args: str) -> int:
    """Compute the candidate-keyspace for a hashcat -a 3 command line."""
    tokens = shlex.split(args)
    custom: dict[int, int] = {}
    mask = ""
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in {"-1", "-2", "-3", "-4"} and i + 1 < len(tokens):
            custom[int(t[1])] = _charset_size(tokens[i + 1], custom)
            i += 2
        elif t in {"-m", "-a"} and i + 1 < len(tokens):
            i += 2
        elif t.startswith("-"):
            i += 1
        else:
            mask = t
            i += 1
    return _mask_size(mask, custom) if mask else 0


def _charset_size(spec: str, custom: dict[int, int]) -> int:
    size = 0
    i = 0
    while i < len(spec):
        if spec[i] == "?" and i + 1 < len(spec):
            c = spec[i + 1]
            if c.isdigit():
                size += custom.get(int(c), 0)
            else:
                size += HASHCAT_CHARSETS.get(c, 0)
            i += 2
        else:
            size += 1
            i += 1
    return size


def _mask_size(mask: str, custom: dict[int, int]) -> int:
    size = 1
    i = 0
    while i < len(mask):
        if mask[i] == "?" and i + 1 < len(mask):
            c = mask[i + 1]
            if c.isdigit():
                size *= custom.get(int(c), 1)
            else:
                size *= HASHCAT_CHARSETS.get(c, 1)
            i += 2
        else:
            i += 1
    return size


def read_rows(path: Path) -> list[Row]:
    rows: list[Row] = []
    with path.open() as f:
        for r in csv.DictReader(f):
            rows.append(
                Row(
                    desc=r["desc"],
                    args=r["hashcat_args"],
                    duration_s=float(r["duration_seconds"]),
                    newly_cracked=int(r["newly_cracked"]),
                    cumulative_cracked=int(r["cumulative_cracked"]),
                    total_hashes=int(r["total_hashes"]),
                    exit_code=int(r["exit_code"]),
                )
            )
    return rows


def humanize_seconds(s: float) -> str:
    if s < 60:
        return f"{s:.1f}s"
    if s < 3600:
        return f"{s / 60:.1f}m"
    if s < 86400:
        return f"{s / 3600:.1f}h"
    if s < 86400 * 365:
        return f"{s / 86400:.1f}d"
    return f"{s / (86400 * 365):.1f}y"


def humanize_keyspace(n: int) -> str:
    if n < 1e6:
        return f"{n:,}"
    if n < 1e9:
        return f"{n / 1e6:.1f}M"
    if n < 1e12:
        return f"{n / 1e9:.1f}B"
    return f"{n / 1e12:.1f}T"


def render_table(rows: list[Row]) -> str:
    head = """
      <thead>
        <tr>
          <th>Mask</th>
          <th class="num">Keyspace</th>
          <th class="num">Time</th>
          <th class="num">Effective rate</th>
          <th class="num">Cracked</th>
        </tr>
      </thead>
    """
    body = []
    for r in rows:
        bar_pct = min(100, (log10(max(r.duration_s, 1)) / log10(86400)) * 100)
        cracked_cls = " cracked" if r.newly_cracked > 0 else ""
        body.append(
            f"""
            <tr class="row{cracked_cls}">
              <td class="mask"><code>{html.escape(r.desc)}</code></td>
              <td class="num">{humanize_keyspace(r.keyspace)}</td>
              <td class="num">
                <div class="bar-wrap">
                  <div class="bar" style="width:{bar_pct:.1f}%"></div>
                  <span>{humanize_seconds(r.duration_s)}</span>
                </div>
              </td>
              <td class="num">{r.effective_rate_mhs:,.0f} MH/s</td>
              <td class="num">{r.newly_cracked} / {r.total_hashes}</td>
            </tr>
            """
        )
    return f'<table class="results">{head}<tbody>{"".join(body)}</tbody></table>'


def projection_chart(rows: list[Row], peak_mhs: float = GPU_PEAK_RATE_MHS) -> str:
    """Inline SVG: actual times for measured mask lengths, projected for 9-12."""
    # Use lowercase+digits configs as the spine. Length is the inferred mask length.
    measured = [(int(r.desc.split("len=")[1].split(" ")[0]), r.duration_s) for r in rows]
    measured.sort()
    if not measured:
        return ""
    # Project lengths beyond what was measured, using 36^L / peak rate.
    base = max(L for L, _ in measured)
    projected: list[tuple[int, float, bool]] = [(L, t, True) for L, t in measured]
    for L in range(base + 1, 13):
        proj_seconds = (36**L) / (peak_mhs * 1e6)
        projected.append((L, proj_seconds, False))

    # Layout
    width, height = 720, 320
    pad_l, pad_r, pad_t, pad_b = 60, 16, 24, 48
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    bar_w = plot_w / len(projected) * 0.65
    gap = plot_w / len(projected) * 0.35
    max_log = log10(max(t for _, t, _ in projected))
    min_log = 0  # 1 second

    bars = []
    labels = []
    for i, (L, t, real) in enumerate(projected):
        x = pad_l + i * (bar_w + gap) + gap / 2
        log_t = log10(max(t, 1))
        h_norm = (log_t - min_log) / (max_log - min_log) if max_log > min_log else 0
        h = max(2, h_norm * plot_h)
        y = pad_t + plot_h - h
        fill = "#0f766e" if real else "#cbd5e1"
        stroke = "#0f766e" if real else "#94a3b8"
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1" rx="2"/>'
        )
        labels.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" '
            f'font-size="11" fill="#334155">{humanize_seconds(t)}</text>'
        )
        labels.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{height - pad_b + 16:.1f}" text-anchor="middle" '
            f'font-size="12" fill="#475569">len={L}</text>'
        )

    # Reference lines
    refs = []
    for label, secs in [("1m", 60), ("1h", 3600), ("1d", 86400), ("1y", 31_557_600)]:
        if secs > 10**max_log:
            continue
        log_s = log10(secs)
        h_norm = (log_s - min_log) / (max_log - min_log)
        y = pad_t + plot_h - h_norm * plot_h
        refs.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
            f'stroke="#e2e8f0" stroke-width="1" stroke-dasharray="3 3"/>'
            f'<text x="{pad_l - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="10" '
            f'fill="#94a3b8">{label}</text>'
        )

    legend = (
        f'<rect x="{pad_l}" y="6" width="10" height="10" fill="#0f766e" rx="2"/>'
        f'<text x="{pad_l + 16}" y="15" font-size="11" fill="#334155">measured</text>'
        f'<rect x="{pad_l + 90}" y="6" width="10" height="10" fill="#cbd5e1" '
        f'stroke="#94a3b8" rx="2"/>'
        f'<text x="{pad_l + 106}" y="15" font-size="11" fill="#334155">'
        f'projected @ {peak_mhs:,} MH/s</text>'
    )

    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Time to exhaust mask vs length" class="chart">'
        f"{''.join(refs)}{''.join(bars)}{''.join(labels)}{legend}</svg>"
    )


def read_hashes() -> list[str]:
    return [ln.strip() for ln in HASH_FILE.read_text().splitlines() if ln.strip()]


def read_solutions() -> list[str]:
    if not SOLUTION_FILE.exists():
        return []
    return [ln.strip() for ln in SOLUTION_FILE.read_text().splitlines() if ln.strip()]


CSS = """
:root {
  --ink: #0f172a;
  --muted: #475569;
  --line: #e2e8f0;
  --bg: #fafaf9;
  --accent: #0f766e;
  --accent-bg: #f0fdfa;
  --code-bg: #f1f5f9;
}
* { box-sizing: border-box; }
html { font-size: 16px; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: var(--ink);
  background: var(--bg);
  line-height: 1.6;
}
.wrap { max-width: 780px; margin: 0 auto; padding: 56px 24px 96px; }
header.hero { padding: 24px 0 40px; border-bottom: 1px solid var(--line); margin-bottom: 40px; }
h1 { font-size: 2.25rem; margin: 0 0 12px; letter-spacing: -0.02em; }
h2 { font-size: 1.35rem; margin: 48px 0 16px; letter-spacing: -0.01em; }
h3 { font-size: 1.05rem; margin: 24px 0 8px; }
p { margin: 0 0 16px; color: var(--ink); }
.lede { font-size: 1.15rem; color: var(--muted); margin-bottom: 24px; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.8rem;
       background: var(--accent-bg); color: var(--accent); border: 1px solid #99f6e4;
       margin-right: 6px; }
code, .mono { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
              font-size: 0.9em; }
code { background: var(--code-bg); padding: 1px 5px; border-radius: 4px; }
pre { background: var(--code-bg); padding: 14px 18px; border-radius: 8px;
      overflow-x: auto; line-height: 1.45; }
pre code { background: transparent; padding: 0; }
a { color: var(--accent); text-decoration: none; border-bottom: 1px solid #99f6e4; }
a:hover { border-bottom-color: var(--accent); }
.verdict {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
  padding: 20px; background: white; border: 1px solid var(--line);
  border-radius: 12px; margin: 24px 0 32px;
}
.verdict .num { font-size: 1.6rem; font-weight: 600; color: var(--accent); display: block; }
.verdict .lbl { font-size: 0.8rem; color: var(--muted); text-transform: uppercase;
                letter-spacing: 0.04em; }
table.results { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.92rem; }
table.results th { text-align: left; padding: 10px 8px; border-bottom: 2px solid var(--line);
                   font-weight: 600; color: var(--muted); font-size: 0.85rem;
                   text-transform: uppercase; letter-spacing: 0.04em; }
table.results td { padding: 12px 8px; border-bottom: 1px solid var(--line);
                   vertical-align: middle; }
table.results td.mask code { background: transparent; padding: 0; }
table.results th.num, table.results td.num { text-align: right; white-space: nowrap; }
table.results tr.cracked td:last-child { color: var(--accent); font-weight: 600; }
.bar-wrap { position: relative; display: inline-block; width: 120px; height: 18px;
            background: #f1f5f9; border-radius: 4px; overflow: hidden; }
.bar-wrap .bar { position: absolute; top: 0; left: 0; bottom: 0;
                 background: var(--accent); opacity: 0.18; }
.bar-wrap span { position: relative; display: block; padding: 0 8px; line-height: 18px;
                 font-size: 0.82rem; text-align: right; }
.chart { width: 100%; height: auto; margin: 8px 0 32px; }
.hash-list { background: white; border: 1px solid var(--line); border-radius: 8px;
             padding: 14px 18px; margin: 16px 0; font-family: ui-monospace, monospace;
             font-size: 0.85rem; line-height: 1.9; }
.hash-list .crack { color: var(--accent); font-weight: 600; }
.hash-list .nope { color: #94a3b8; }
.callout { padding: 14px 18px; background: var(--accent-bg); border-left: 3px solid var(--accent);
           border-radius: 4px; margin: 24px 0; }
footer { margin-top: 64px; padding-top: 24px; border-top: 1px solid var(--line);
         color: var(--muted); font-size: 0.9rem; }
@media (max-width: 540px) {
  h1 { font-size: 1.7rem; }
  .verdict { grid-template-columns: 1fr; }
  .bar-wrap { width: 80px; }
}
"""


def render() -> str:
    rows = read_rows(RESULTS_CSV)
    hashes = read_hashes()
    solutions = set(read_solutions())

    # Match cracked plaintexts to hashes via the potfile if present.
    potfile = ROOT / "runs" / "hashcat.potfile"
    cracked_map: dict[str, str] = {}
    if potfile.exists():
        for line in potfile.read_text().splitlines():
            if ":" in line:
                h, _, p = line.partition(":")
                cracked_map[h.strip()] = p.strip()

    total_hashes = max(r.total_hashes for r in rows) if rows else len(hashes)
    cracked_total = max(r.cumulative_cracked for r in rows) if rows else 0
    fastest = min(rows, key=lambda r: r.duration_s) if rows else None
    slowest = max(rows, key=lambda r: r.duration_s) if rows else None

    hash_list_html = []
    for h in hashes:
        plain = cracked_map.get(h)
        if plain:
            hash_list_html.append(
                f'<div><span class="crack">{html.escape(h)} → {html.escape(plain)}</span></div>'
            )
        else:
            hash_list_html.append(
                f'<div><span class="nope">{html.escape(h)} → uncracked</span></div>'
            )

    table_html = render_table(rows)
    chart_svg = projection_chart(rows)

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cracking SHA-1 on a Grace Blackwell GPU</title>
<meta name="description" content="What does it actually take to crack short bare SHA-1 hashes on a 2025-era NVIDIA GB10 GPU? A short investigation with timings.">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<header class="hero">
  <span class="tag">SHA-1</span><span class="tag">hashcat</span><span class="tag">{html.escape(GPU_MODEL)}</span>
  <h1>How fast does a Grace Blackwell GPU chew through unsalted SHA-1?</h1>
  <p class="lede">
    A short, hands-on investigation: stage mask attacks of increasing keyspace against
    three short synthetic passwords, measure where the wall is, and watch the cost curve.
  </p>
</header>

<section>
  <p>
    When a service gets breached, the leaked database usually contains password
    <em>hashes</em>, not the passwords themselves &mdash; a hash is a one-way function: easy
    to compute forward, infeasible to reverse directly. But anyone holding the hashes can
    guess passwords offline at GPU speed and check each guess against the leak. Whether
    that takes seconds or geological time depends entirely on <em>how</em> the passwords
    were hashed. This is a look at what "GPU speed" actually means in 2026, against the
    weakest end of that spectrum: a single round of bare unsalted SHA-1.
  </p>
</section>

<section>
  <div class="verdict">
    <div><span class="num">{cracked_total}/{total_hashes}</span>
         <span class="lbl">hashes cracked</span></div>
    <div><span class="num">{humanize_seconds(fastest.duration_s) if fastest else "—"}</span>
         <span class="lbl">fastest mask</span></div>
    <div><span class="num">{humanize_seconds(slowest.duration_s) if slowest else "—"}</span>
         <span class="lbl">slowest measured</span></div>
  </div>
</section>

<section>
  <h2>The targets</h2>
  <p>Three synthetic 8-character passwords, hashed with a single round of bare unsalted SHA-1
     (<code>-m 100</code>). They span the realistic surface that a hashcat mask attack can
     reach: pure lowercase + digits, mixed case, and symbol-flanked.</p>
  <div class="hash-list">{"".join(hash_list_html)}</div>
  <p class="lede">One fell. The other two survived this round &mdash; not because the hash is strong, but
     because the keyspace their pattern lives in is much bigger.</p>
</section>

<section>
  <h2>Methodology</h2>
  <p>A <strong>mask attack</strong> tells hashcat the shape of the password, not the password
     itself, then enumerates every candidate that fits that shape. The shapes are stacked
     cheapest-first:</p>
  <ol>
    <li><strong>Lowercase + digits</strong>, lengths 6&ndash;9. Charset of 36, keyspace grows
        as 36<sup>L</sup>. Catches things like <code>tabletop</code> or <code>2faster</code>.</li>
    <li><strong>Upper-prefixed</strong> &mdash; one capital up front, rest lowercase+digit.
        Catches the <code>Password1</code>-style pattern.</li>
    <li><strong>Symbol-flanked</strong> &mdash; uppercase/lowercase/symbol at the edges,
        lowercase+digit in the middle. The kind of "complex" password humans actually
        generate when forced to use symbols.</li>
  </ol>
  <p>This ordering matters: each step multiplies the keyspace by something like 30&ndash;100,
     so the cost grows fast. You burn the cheap masks first because they take seconds, and you
     only commit GPU-days to the expensive ones if you have to.</p>
</section>

<section>
  <h2>Results</h2>
  <p>What actually happened on the GB10:</p>
  {table_html}
  <p>The 8-character lowercase-and-digits mask is where the first crack landed:
     <code class="mono">tabletop</code>, a dictionary word. It took {humanize_seconds(slowest.duration_s) if slowest else "an hour"}.
     The next step in that family &mdash; length 9 with the same charset &mdash; would have
     taken roughly a day and a half. At that point the right answer isn't "throw more
     hashcat at it," it's "this mask family is wrong."</p>
</section>

<section>
  <h2>The cost curve</h2>
  <p>Same charset (lowercase + digits), one extra character at a time. Each step multiplies
     the keyspace by 36, so on a log axis it's a straight line. The teal bars are measured;
     the gray bars are projected at the GB10's observed peak rate of
     {GPU_PEAK_RATE_MHS:,} MH/s.</p>
  {chart_svg}
  <div class="callout">
    <strong>Takeaway.</strong> Picking symbols doesn't save you. <em>Length</em> saves you.
    Going from 8 to 12 lowercase-and-digit characters &mdash; same boring charset, just longer
    &mdash; moves "an hour on a beefy GPU" to "longer than anyone reading this will be
    alive." And that's before salting, before a slow KDF, before any of the things a real
    password store should be doing.
  </div>
</section>

<section>
  <h2>Hardware</h2>
  <p>The GPU is an <strong>{html.escape(GPU_MODEL)}</strong> &mdash; NVIDIA's 2025 ARM-based
     workstation chip with unified CPU/GPU memory. Hashcat doesn't ship an ARM64 binary, so the
     setup script in the repo builds 7.1.2 from source against the system CUDA toolkit.
     Across the sweep it sustained ~{GPU_PEAK_RATE_MHS:,} MH/s on bare SHA-1.</p>
</section>

<section>
  <h2>Reproduce</h2>
<pre><code>git clone {REPO_URL}
cd hash_cracking
bash setup.sh                                      # builds hashcat 7.1.2 from source
export HASHCAT_BIN=$HOME/hashcat-7.1.2/hashcat
uv sync
uv run hash-cracking</code></pre>
  <p>Results stream to <code>results.csv</code> and per-config logs to <code>runs/</code>.
     Re-running <code>python build_site.py</code> regenerates this page from the CSV.</p>
</section>

<footer>
  Investigation writeup: <a href="{BLOG_URL}">scheuclu.com/posts/password_hash_crack</a> &middot;
  Source: <a href="{REPO_URL}">github.com/scheuclu/hash_cracking</a>
</footer>

</div>
</body>
</html>
"""
    return page


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
