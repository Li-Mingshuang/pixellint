"""Solve a scene's object placement against the composition rules.

Hand-placing twenty objects and re-running the check after each nudge is tedium,
and tedium is where a layout quietly ends up violating a rule nobody re-checked.
So this splits the job the way it actually divides:

  * **depth band** -- which base row an object stands on -- is an art decision.
    It sets occlusion order and the reading of near/far. A human picks it.
  * **x position** within a band is a constraint-satisfaction problem. This solves
    it, greedily, against the same rule `check_scene.py` enforces.

The rule, from the scene spec's `composition` block: two objects may share a
colour, or stand close together, but not both. "Close together" means close in x
AND close in depth -- a foreground barrel and a background fence read as separate
things even when they overlap in x.

    python plan_scene.py --dry-run     # show the plan, do not write
    python plan_scene.py               # rewrite scenes/meadow.json

Never silently: if a band is too crowded to satisfy the rule, this refuses to
place the object and says so rather than dropping it or overlapping anyway.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "game"))

# name -> (module, attribute, width, height). Widths come from the art modules;
# they are read at runtime so a redrawn prop cannot silently invalidate a layout.
SOURCES = {
    "tree": ("props", "TREE"), "house": ("props", "HOUSE"),
    "fence": ("props", "FENCE"), "rock": ("props", "ROCK"),
    "tree2": ("props", "TREE"), "fence2": ("props", "FENCE"),
    "rock2": ("props", "ROCK"),
    "barrel": ("farmprops", "BARREL"), "crate": ("farmprops", "CRATE"),
    "signpost": ("farmprops", "SIGNPOST"), "stump": ("farmprops", "STUMP"),
    "logpile": ("farmprops", "LOGPILE"), "milkchurn": ("farmprops", "MILKCHURN"),
    "bush": ("foliage", "BUSH"), "flowers": ("foliage", "FLOWERPATCH"),
    "mushrooms": ("foliage", "MUSHROOMS"), "chicken": ("foliage", "CHICKEN"),
    "well": ("yardprops", "WELL"), "haystack": ("yardprops", "HAYSTACK"),
    "scarecrow": ("yardprops", "SCARECROW"), "wagon": ("yardprops", "WAGON"),
}

# name -> grid attribute or list attribute
ANIMATED = {"farmer": ("walk_cycle", "FRAMES"), "dog": ("dog", "DOG_FRAMES"),
            "chicken": ("foliage", "CHICKEN")}


def load_grid(module_name, attr):
    try:
        mod = __import__(module_name)
    except Exception as exc:
        return None, f"{module_name}: {exc}"
    val = getattr(mod, attr, None)
    if val is None:
        return None, f"{module_name}.{attr} missing"
    if isinstance(val, list) and val and isinstance(val[0], list) \
            and val[0] and isinstance(val[0][0], str):
        val = val[0]          # a clip: take frame 0 for footprint purposes
    return val, None


def colours_of(grid, ignore):
    return {c for row in grid for c in row if c != "."} - set(ignore)


def solve(spec, plan, verbose=True):
    """plan: list of (name, module, attr, base_row, x_hint)."""
    comp = spec.get("composition", {})
    min_gap = comp.get("min_gap", 8)
    depth_close = comp.get("depth_close", 8)
    need_shared = comp.get("shared_colours", 2)
    ignore = comp.get("ignore_colours", ["K"])
    W = spec["size"][0]

    placed, problems = [], []
    for name, module, attr, base, hint in plan:
        grid, err = load_grid(module, attr)
        if err:
            problems.append(f"{name}: {err}")
            continue
        w = len(grid[0])
        cols = colours_of(grid, ignore)

        def ok(x):
            if x < 0 or x + w > W:
                return False
            for p in placed:
                shared = cols & p["colours"]
                if len(shared) < need_shared:
                    continue
                gap = max(x - (p["x"] + p["width"]), p["x"] - (x + w))
                dz = abs(base - p["base"])
                if gap < min_gap and dz < depth_close:
                    return False
            return True

        # search outward from the hint so the layout stays close to the intent
        chosen = None
        order = sorted(range(W - w + 1), key=lambda x: (abs(x - hint), x))
        for x in order:
            if ok(x):
                chosen = x
                break
        if chosen is None:
            problems.append(f"{name}: no free x in a {W}px canvas at base {base} "
                            f"({w}px wide) satisfying the composition rules")
            if verbose:
                print(f"  FAIL  {name}: could not place")
            continue

        placed.append({"name": name, "module": module, "attr": attr,
                       "x": chosen, "base": base, "width": w, "colours": cols})
        if verbose:
            moved = "" if chosen == hint else f"  (hint {hint} -> {chosen})"
            print(f"  ok    {name:<10} x={chosen:>3}..{chosen + w - 1:<3} base={base}  "
                  f"{w}px{moved}")
    return placed, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--spec", default=str(HERE / "scenes" / "meadow.json"))
    args = ap.parse_args()

    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    plan = [(l["name"], l["module"], l["attr"], l["base"], l["x"])
            for l in spec["layers"] if "base" in l and "x" in l]
    print(f"solving {len(plan)} objects in a {spec['size'][0]}px canvas\n")
    placed, problems = solve(spec, plan)

    print(f"\nplaced {len(placed)}/{len(plan)}")
    if problems:
        for p in problems:
            print(f"  UNRESOLVED  {p}")
        print("\nnot writing: a plan with unresolved objects is worse than the "
              "one already on disk")
        return 1

    if args.dry_run:
        print("\n--dry-run: spec not written")
        return 0

    by_name = {p["name"]: p for p in placed}
    for layer in spec["layers"]:
        if layer.get("name") in by_name:
            layer["x"] = by_name[layer["name"]]["x"]
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"\nwrote {spec_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
