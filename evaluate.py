"""Measure the pipeline instead of merely gating it.

Every other script in this repo answers "is it acceptable". This one answers
"how much did it cost, and how much room was there to spare" -- which are
different questions, and the second one is the one you need in order to reason
about a *harder* target before you attempt it.

    python evaluate.py                 # measure and print a report
    python evaluate.py --json          # also write evaluation.json
    python evaluate.py --markdown      # also write EVALUATION.md

What is measured, per asset:

  cells       w * h * frames. The size of the authoring surface, and the closest
              thing there is to a cost driver for a model writing text grids.
  keys        distinct palette entries actually used. Palette juggling load.
  pairs       adjacent colour pairs the separation rule had to adjudicate.
  margin      min over touching pairs of (dE - floor), in dE units. This is how
              much slack the artist had; a margin near zero means the palette was
              fighting the picture. Negative is a hard failure.
  warnings    pairs that are close but visible. Advisory by design.
  struct      structural problems (floating pixels, unclosed outline, ...).
  check_ms    wall time to run the structural + separation checks on it.

What is deliberately NOT claimed here: any measure of whether the art is
*beautiful*. There is no such metric, this script does not invent one, and a
green evaluation is not an aesthetic verdict. See the "what these numbers are
not" section of the report it prints.
"""

import argparse
import importlib
import json
import sys
import time
import traceback
from pathlib import Path

from gamepalette import GAME_PALETTE
from pixelkit import (SCENE_PALETTE, SEP_RULES, VALUE_RATIO, VALUE_STEP,
                      adjacent_pairs, check_grid, luminance, reads_by_value,
                      verdict)

HERE = Path(__file__).resolve().parent


def _import(name, *paths):
    for p in paths:
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    for p in paths:
        if str(p) in sys.path:
            sys.path.remove(str(p))
        sys.path.insert(0, str(p))
    return importlib.import_module(name)


# Modules that may export art. Anything grid-shaped found in them is measured, so
# adding an art module does not require editing this file -- the same lesson as
# build.py's recursive check discovery: a hand-maintained list silently omits the
# newest thing, and the omission looks like a clean report.
ART_MODULES = [
    ("meadow", "render_sprite"), ("meadow", "walk_cycle"), ("meadow", "ground"),
    ("meadow", "props"), ("meadow", "sky"), ("meadow", "dog"),
    ("meadow", "farmprops"), ("meadow", "foliage"), ("meadow", "yardprops"),
    ("game", "background"), ("game", "player"), ("game", "zombie"),
    ("game", "effects"),
]


# Composition blocks, not deliverables. walk_cycle.FRAMES is ASSEMBLED from these,
# so measuring both would double-count the same authored cells. This list is a
# wart: the honest fix is for each module to declare its exports (an `__all__` or
# a SHIPPED tuple) and for this to read that instead. It is listed here, visibly,
# rather than hidden by a naming convention.
INTERNAL_BLOCKS = {
    "HEAD", "HEAD_DOWN", "TORSO", "TORSO_LEFT_ARM_FWD", "TORSO_RIGHT_ARM_FWD",
    "LEGS_PLANTED", "LEGS_LIFT_LEFT", "LEGS_LIFT_RIGHT",
}


def _is_grid(v):
    """list[str] of equal length, drawn from palette-ish characters."""
    return (isinstance(v, list) and 2 <= len(v)
            and all(isinstance(r, str) and len(r) == len(v[0]) for r in v)
            and all(c.isalnum() or c == "." for r in v for c in r))


def _is_clip(v):
    return (isinstance(v, list) and v and all(_is_grid(f) for f in v))


def discover():
    """Every (group, module, name, [frames]) the repo ships, found by shape."""
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE / "game"))
    out, skipped = [], []

    for group, module_name in ART_MODULES:
        try:
            mod = importlib.import_module(module_name)
        except Exception as exc:
            skipped.append((group, module_name, f"{type(exc).__name__}: {exc}"))
            continue

        def add(name, value, top=True):
            if name in INTERNAL_BLOCKS:
                return
            if _is_clip(value):
                out.append((group, module_name, name, list(value)))
            elif _is_grid(value):
                out.append((group, module_name, name, [value]))
            elif isinstance(value, dict):
                for k, v in value.items():
                    # a container is a bag of deliverables, so its keys are the
                    # names -- "PLAYER.walk" not "PLAYER.PLAYER.walk"
                    add(str(k), v, top=False)

        for attr in dir(mod):
            if attr.startswith("_"):
                continue
            value = getattr(mod, attr)
            if callable(value):
                continue
            add(attr, value)

    # de-duplicate by content: a module often aliases one grid under two names,
    # and TREE may appear both bare and inside PROPS
    seen, unique = set(), []
    for group, module, name, frames in out:
        key = (group, module, tuple(f[0] + "|" + str(len(f)) + "|" + f[-1]
                                    for f in frames), len(frames))
        if key in seen:
            continue
        seen.add(key)
        # prefer the shortest name (the bare export over the container path)
        unique.append((group, module, name, frames))
    return unique, skipped


def tier_of(cells: int) -> str:
    for limit, name in ((1024, "XS"), (4096, "S"), (16384, "M"),
                        (65536, "L")):
        if cells <= limit:
            return name
    return "XL"


def measure(grid, palette) -> dict:
    """All the numbers for one grid.

    `margin` is RELATIVE: 0.0 means the pair sits exactly on its threshold, 0.5
    means it clears it by half again. It has to be relative because a pair can
    pass by either of two mechanisms with different units -- chroma (dE against a
    floor) or a lightness edge (a ratio against 1.7). An earlier version reported
    `max(d - floor, 0)`, which silently flattened every value-governed pair to
    0.00 and made a healthy sky gradient look like it was failing.
    """
    w, h = len(grid[0]), len(grid)
    t0 = time.perf_counter()
    struct = check_grid(grid, "", palette)
    pairs = adjacent_pairs(grid, palette)
    margins, warnings, failures, by_value = [], 0, 0, 0
    for a, b in pairs:
        v, d, dl = verdict(a, b, palette)
        role = "outline" if "K" in (a, b) else "fill"
        floor = SEP_RULES[role]["fail"]
        la, lb = luminance(a, palette), luminance(b, palette)
        if reads_by_value(la, lb):
            by_value += 1
            hi, lo = max(la, lb), min(la, lb)
            step = (hi - lo - VALUE_STEP) / VALUE_STEP
            ratio = (hi / lo - VALUE_RATIO) / VALUE_RATIO if lo > 0 else 0.0
            margins.append(max(step, ratio))
            continue
        margins.append((d - floor) / floor)
        if v == "fail":
            failures += 1
        elif v == "warn":
            warnings += 1
    ms = (time.perf_counter() - t0) * 1000
    keys = {c for row in grid for c in row if c != "."}
    return {
        "w": w, "h": h, "cells": w * h,
        "keys": len(keys), "pairs": len(pairs), "by_value": by_value,
        "margin": round(min(margins), 3) if margins else None,
        "mean_margin": round(sum(margins) / len(margins), 3) if margins else None,
        "warnings": warnings, "failures": failures,
        "struct": len(struct), "struct_msg": struct[0] if struct else None,
        "check_ms": round(ms, 2),
    }


def attempt_stats(log: Path) -> dict:
    """Per check script: attempts before its most recent success.

    This is the closest thing here to a difficulty measure. `cells` measures the
    authoring surface and the colour margin measures palette slack; neither says
    how much iteration a target actually cost. The build appends every check
    outcome to `.pipeline-runs.jsonl`, so "it took nine tries to go green" is
    recoverable -- but only from runs that happened after logging was added, and
    only per SCRIPT, not per asset. Both limits are stated in the report rather
    than glossed.
    """
    if not log.exists():
        return {}
    entries = []
    for line in log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    by_script: dict[str, list[bool]] = {}
    for e in entries:
        by_script.setdefault(e.get("script", "?"), []).append(bool(e.get("ok")))

    out = {}
    for script, oks in by_script.items():
        if script == "__build__" or True not in oks:
            continue
        last = len(oks) - 1 - oks[::-1].index(True)
        back = 0
        i = last - 1
        while i >= 0 and not oks[i]:
            back += 1
            i -= 1
        out[script] = {"attempts_to_green": back + 1, "total_runs": len(oks),
                       "failures_total": oks.count(False)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()

    assets, load_skipped = discover()
    if not assets:
        print("no assets discovered")
        return 1

    rows, skipped = [], list(load_skipped)
    for group, mod, name, frames in assets:
        palette = GAME_PALETTE if group == "game" else SCENE_PALETTE
        try:
            per = [measure(g, palette) for g in frames]
        except Exception as exc:
            skipped.append((group, mod, name, f"{type(exc).__name__}: {exc}"))
            continue
        cells = sum(p["cells"] for p in per)
        worst = min((p["margin"] for p in per if p["margin"] is not None), default=None)
        rows.append({
            "group": group, "module": mod, "name": name, "frames": len(frames),
            "w": per[0]["w"], "h": per[0]["h"],
            "cells": cells,
            "tier": tier_of(cells),
            "keys": max(p["keys"] for p in per),
            "pairs": sum(p["pairs"] for p in per),
            "by_value": sum(p["by_value"] for p in per),
            "margin": worst,
            "mean_margin": round(sum(p["mean_margin"] or 0 for p in per) / len(per), 3),
            "warnings": sum(p["warnings"] for p in per),
            "failures": sum(p["failures"] for p in per),
            "struct": sum(p["struct"] for p in per),
            "struct_msg": next((p["struct_msg"] for p in per if p["struct_msg"]), None),
            "check_ms": round(sum(p["check_ms"] for p in per), 2),
        })

    # ---- report ----------------------------------------------------------
    print("=" * 96)
    print("PIPELINE EVALUATION")
    print("=" * 96)

    for group in ("meadow", "game"):
        rs = [r for r in rows if r["group"] == group]
        if not rs:
            continue
        print(f"\n-- {group} " + "-" * (92 - len(group)))
        print(f"  {'asset':<22} {'size':>9} {'fr':>3} {'tier':>4} {'cells':>8} "
              f"{'keys':>4} {'pairs':>5} {'margin':>7} {'warn':>4} {'FAIL':>4} {'ms':>7}")
        for r in sorted(rs, key=lambda r: -r["cells"]):
            m = "  n/a" if r["margin"] is None else f"{r['margin']:>7.2f}"
            print(f"  {r['module'] + '.' + r['name']:<22} "
                  f"{str(r['w']) + 'x' + str(r['h']):>9} {r['frames']:>3} {r['tier']:>4} "
                  f"{r['cells']:>8} {r['keys']:>4} {r['pairs']:>5} {m} "
                  f"{r['warnings']:>4} {r['failures']:>4} {r['check_ms']:>7.1f}")

    print("\n-- by complexity tier " + "-" * 73)
    print(f"  {'tier':>4} {'assets':>6} {'frames':>7} {'cells':>9} {'keys':>5} "
          f"{'pairs':>6} {'min margin':>11} {'mean ms':>8} {'ms/1k cells':>12}")
    tiers = {}
    for r in rows:
        tiers.setdefault(r["tier"], []).append(r)
    for t in ("XS", "S", "M", "L", "XL"):
        rs = tiers.get(t)
        if not rs:
            continue
        cells = sum(r["cells"] for r in rs)
        ms = sum(r["check_ms"] for r in rs)
        margins = [r["margin"] for r in rs if r["margin"] is not None]
        print(f"  {t:>4} {len(rs):>6} {sum(r['frames'] for r in rs):>7} {cells:>9} "
              f"{max(r['keys'] for r in rs):>5} {sum(r['pairs'] for r in rs):>6} "
              f"{min(margins):>11.2f} {ms / len(rs):>8.1f} "
              f"{ms / max(cells, 1) * 1000:>12.2f}")

    total_cells = sum(r["cells"] for r in rows)
    total_pairs = sum(r["pairs"] for r in rows)
    total_ms = sum(r["check_ms"] for r in rows)
    # Only hard colour failures are this script's business. Structural notes are
    # reported separately and are often EXPECTED -- a skyline made of separate
    # buildings reports floating pixels by definition, because check_grid requires
    # one connected body. Treating those as a non-zero exit made the report look
    # like a failure on every run.
    bad = [r for r in rows if r["failures"]]
    print("\n-- totals " + "-" * 85)
    print(f"  assets           : {len(rows)}  ({sum(r['frames'] for r in rows)} grids)")
    print(f"  cells authored   : {total_cells:,}")
    print(f"  pairs adjudicated: {total_pairs:,}")
    print(f"  check wall time  : {total_ms:.0f} ms  "
          f"({total_ms / max(total_cells, 1) * 1000:.3f} ms per 1k cells)")
    print(f"  hard failures    : {sum(r['failures'] for r in rows)}")
    print(f"  structural       : {sum(r['struct'] for r in rows)}")
    print(f"  warnings         : {sum(r['warnings'] for r in rows)}")
    print(f"  assets clean     : {len(rows) - len(bad)}/{len(rows)}")

    if skipped:
        print("\n  skipped (import failed):")
        for g, m, n, why in skipped:
            print(f"    {g}/{m}.{n}: {why}")

    noted = [r for r in rows if r["struct"]]
    if noted:
        print("\n-- structural notes (not necessarily defects) " + "-" * 49)
        for r in noted:
            print(f"  {r['module']}.{r['name']}: {r['struct_msg']}")
        print("  NOTE: a layer made of SEPARATE objects -- a skyline, a cloud band --")
        print("  reports floating pixels by definition, because check_grid requires one")
        print("  connected body. Those layers prove their real structure with a cyclic")
        print("  flood fill instead; see game/check_background.py and check_sky.py.")

    stats = attempt_stats(HERE / ".pipeline-runs.jsonl")
    if stats:
        print("\n-- iteration, per check script " + "-" * 62)
        print(f"  {'script':<34} {'attempts to green':>17} {'total runs':>11} {'failures':>9}")
        for script, s in sorted(stats.items(),
                                key=lambda kv: -kv[1]["attempts_to_green"]):
            print(f"  {script:<34} {s['attempts_to_green']:>17} "
                  f"{s['total_runs']:>11} {s['failures_total']:>9}")
        print("  Attempts to green is consecutive failures before the most recent")
        print("  success. It is the closest thing here to a difficulty measure, and it")
        print("  is limited: it only covers runs since logging was added, and it is per")
        print("  SCRIPT, not per asset.")
    else:
        print("\n-- iteration " + "-" * 81)
        print("  no run log yet. build.py appends every check outcome to")
        print("  .pipeline-runs.jsonl, so this fills in from the next build onwards.")

    print("\n-- what these numbers are NOT " + "-" * 64)
    print("  * 'margin' is readability slack, not beauty. An asset can sit far")
    print("    above every floor and still be ugly; the pipeline cannot tell.")
    print("  * 'cells' is an authoring-surface proxy, not difficulty. A 30,720-cell")
    print("    sky gradient is far easier than a 512-cell face, because the gradient")
    print("    was procedural and the face was reasoned about cell by cell.")
    print("  * check_ms measures the ASSERTION cost only. It excludes the cost of")
    print("    authoring the art, which is where the real spend is and which this")
    print("    repo does not instrument at all.")

    if args.json:
        p = HERE / "evaluation.json"
        p.write_text(json.dumps({
            "assets": rows, "skipped": skipped,
            "totals": {"assets": len(rows), "cells": total_cells,
                       "pairs": total_pairs, "check_ms": round(total_ms, 1),
                       "failures": sum(r["failures"] for r in rows),
                       "warnings": sum(r["warnings"] for r in rows)},
        }, indent=2), encoding="utf-8")
        print(f"\nwrote {p}")

    if args.markdown:
        p = HERE / "EVALUATION.md"
        lines = ["# Pipeline evaluation", "",
                 f"{len(rows)} assets, {total_cells:,} cells, {total_pairs:,} "
                 f"adjacent colour pairs adjudicated.", "",
                 "| asset | size | frames | tier | cells | keys | pairs | min margin | warnings | failures | check ms |",
                 "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sorted(rows, key=lambda r: (r["group"], -r["cells"])):
            m = "n/a" if r["margin"] is None else f"{r['margin']:.2f}"
            lines.append(f"| `{r['module']}.{r['name']}` | {r['w']}x{r['h']} | "
                         f"{r['frames']} | {r['tier']} | {r['cells']} | {r['keys']} | "
                         f"{r['pairs']} | {m} | {r['warnings']} | {r['failures']} | "
                         f"{r['check_ms']:.1f} |")
        lines += ["", "## Iteration", "",
                  "Attempts-to-green is consecutive failures before a check's most "
                  "recent success, read from `.pipeline-runs.jsonl`. It is the closest "
                  "thing here to a difficulty measure, and it is limited: it covers "
                  "only runs since logging was added, and it is per script rather than "
                  "per asset.", "",
                  "| script | attempts to green | total runs | failures |",
                  "|---|---|---|---|"]
        for script, s in sorted(attempt_stats(HERE / ".pipeline-runs.jsonl").items(),
                                key=lambda kv: -kv[1]["attempts_to_green"]):
            lines.append(f"| `{script}` | {s['attempts_to_green']} | "
                         f"{s['total_runs']} | {s['failures_total']} |")
        lines += ["", "## What these numbers are not", "",
                  "- **margin is readability slack, not beauty.** An asset can sit far "
                  "above every floor and still be ugly. The pipeline cannot tell.",
                  "- **cells is an authoring-surface proxy, not difficulty.** A "
                  "30,720-cell sky gradient is far easier than a 512-cell face, because "
                  "the gradient was procedural and the face was reasoned about cell by "
                  "cell.",
                  "- **check_ms is assertion cost only.** It excludes authoring cost, "
                  "which is where the real spend is and which this repo does not "
                  "instrument at all."]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {p}")

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
