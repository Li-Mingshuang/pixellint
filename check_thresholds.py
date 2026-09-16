"""Pin the separation rule itself, with synthetic inputs.

Testing the rule against the live palette is not a test: the palette gets fixed,
the pair that used to fail starts passing, and the "regression test" silently
stops testing anything. So these cases are synthetic (dE, luminance-a,
luminance-b) triples. They pin the RULE, and they are what stops a future tweak
from quietly turning the check off.

The rule under test:

    readable  <=>  a lightness edge  (|dL| >= VALUE_STEP, or ratio >= VALUE_RATIO)
                   OR  dE >= the role's chroma floor

The ratio half exists because perception follows Weber's law. In a night palette
0.05 against 0.16 is a three-fold brightness difference and reads instantly,
while the same absolute gap up in the midtones is barely visible. An earlier
rule used the absolute step alone and declared honest night palettes unreadable.
"""

from pixelkit import (SEP_RULES, VALUE_RATIO, VALUE_STEP, reads_by_value, verdict)

# A tiny synthetic palette so real colours can be driven through the rule.
PAL = {
    ".": (0, 0, 0, 0),
    # luminance ladder (sRGB values chosen to hit these greys)
    "A": (0, 0, 0, 255),
    "B": (13, 13, 13, 255),      # ~0.05
    "C": (41, 41, 41, 255),      # ~0.16
    "D": (110, 110, 110, 255),   # ~0.43
    "E": (170, 170, 170, 255),   # ~0.66
    "F": (250, 250, 250, 255),   # ~0.98
    # same lightness, wildly different hue (the overalls-vs-shirt case)
    "G": (200, 160, 90, 255),
    "H": (60, 100, 200, 255),
    # a near-identical pair
    "I": (128, 128, 128, 255),
    "J": (133, 133, 131, 255),
}

CASES = [
    # (a, b, expect, what it represents)
    ("A", "A", "fail", "degenerate: a colour against itself"),

    # --- value-ratio escapes, the night-palette case --------------------
    ("B", "C", "ok", "0.05 vs 0.16: 3.2x lightness, reads instantly in the dark"),
    ("C", "D", "ok", "0.16 vs 0.43: 2.7x lightness"),
    ("D", "E", "ok", "adjacent midtones, still a clear step"),
    ("A", "B", "fail", "near-black against black: dE 3.6, no real edge at either end"),
    ("C", "B", "ok", "0.16 vs 0.05: 3.2x lightness downward"),

    # --- chroma escapes -------------------------------------------------
    ("G", "H", "ok", "overalls vs shirt: near-identical lightness, opposite hue"),

    # --- the genuinely unreadable ---------------------------------------
    ("I", "J", "fail", "two greys 5 sRGB units apart: no lightness edge, no chroma"),
    ("D", "E", "ok", "sanity: a real step never fails"),

    # --- outline strictness ---------------------------------------------
    ("H", "I", "ok", "blue vs mid grey: hue alone at dE 60 is plenty"),
]


def main() -> int:
    print(f"rule: readable iff  |dL| >= {VALUE_STEP}  or  ratio >= {VALUE_RATIO}  "
          f"or  dE >= role floor")
    print(f"floors: outline {SEP_RULES['outline']['fail']:.0f}, "
          f"fill {SEP_RULES['fill']['fail']:.0f}")
    print(f"{'expect':<8} {'got':<8} {'dE':>6} {'dL':>6}  case")
    failures = 0
    for a, b, expect, note in CASES:
        got, d, dl = verdict(a, b, PAL)
        # 'warn' and 'ok' are both passes; only 'fail' is a rejection
        got_pass = got != "fail"
        exp_pass = expect != "fail"
        ok = got_pass == exp_pass
        failures += 0 if ok else 1
        print(f"{expect:<8} {got:<8} {d:>6.1f} {dl:>6.3f}  "
              f"{'' if ok else 'MISMATCH  '}{note}")

    print()
    print("value-ratio checks:")
    for lo, hi, want in ((0.05, 0.16, True), (0.05, 0.09, True),
                         (0.30, 0.60, True), (0.30, 0.40, False),
                         (0.001, 0.010, False)):
        got = reads_by_value(lo, hi)
        mark = "ok  " if got == want else "WRONG"
        failures += 0 if got == want else 1
        print(f"  {mark} {lo:.3f} vs {hi:.3f} -> {got} (want {want})")

    print()
    if failures:
        print(f"{failures} case(s) disagree with the rule's intent -- the check has drifted")
        return 1
    print(f"ok - all {len(CASES)} colour cases and 5 ratio cases behave as intended")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
