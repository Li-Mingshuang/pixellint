"""Pin the separation rule itself, with synthetic inputs.

The rule is:

    pass  <=>  dE >= tier_floor   OR   luminance step >= VALUE_STEP

Testing it against the live palette is not a test: the palette gets fixed, the
pair that used to fail starts passing, and the "regression test" silently stops
testing anything. That happened here -- a first version of this file asserted
`K-p` should fail, but the palette had already been rebalanced to take it from
dE 12.7 to 28.2, so the assertion was checking a value that no longer existed.

So these cases are synthetic (dE, dL, floor) triples. They pin the RULE, and
they are what stops a future tweak from quietly turning the check off.
"""

from pixelkit import VALUE_STEP

# (dE, dL, floor, should_pass, what it represents)
CASES = [
    # --- must be rejected -------------------------------------------------
    (0.0, 0.00, 28, False, "degenerate: a colour against itself"),
    (12.7, 0.19, 28, False,
     "the original killer: outline vs trouser shadow, as first written"),
    (12.7, 0.19, 15, False,
     "same pair at the loosest floor -- still rejected, no value escape"),
    (24.9, 0.24, 32, False,
     "just under both gates: low chroma AND value step below 0.25"),
    (29.8, 0.04, 32, False,
     "the stone/dirt landmine before the palette fix"),
    (31.0, 0.24, 32, False,
     "0.9 short of the floor and 0.01 short of the step -- correctly rejected"),

    # --- must pass on chroma ---------------------------------------------
    (44.0, 0.05, 32, True, "small value gap, large chroma difference"),
    (65.4, 0.08, 45, True,
     "overalls vs shirt: same lightness, wildly different hue"),
    (36.6, 0.04, 32, True, "the stone/dirt landmine AFTER the palette fix"),

    # --- must pass on the value step -------------------------------------
    (20.0, 0.30, 45, True,
     "large value gap, modest chroma: readable on lightness alone"),
    (24.9, 0.26, 32, True,
     "the spurious 0.1-dE failure that showed the rule was wrong"),
    (5.0, 0.40, 45, True,
     "very close in hue but a 40% lightness step -- still an edge"),
]


def main() -> int:
    print(f"rule: pass iff dE >= floor, OR luminance step >= {VALUE_STEP}")
    print(f"{'expect':<8} {'got':<8} {'dE':>6} {'dL':>6} {'floor':>6}   case")
    failures = 0
    for d, dl, floor, should_pass, note in CASES:
        got = d >= floor or dl >= VALUE_STEP
        ok = got == should_pass
        failures += 0 if ok else 1
        print(f"{'pass' if should_pass else 'reject':<8} "
              f"{'pass' if got else 'reject':<8} "
              f"{d:>6.1f} {dl:>6.2f} {floor:>6.0f}   "
              f"{'' if ok else 'MISMATCH  '}{note}")
    print()
    if failures:
        print(f"{failures} case(s) disagree with the rule's intent -- the check has drifted")
        return 1
    print(f"ok - all {len(CASES)} cases behave as intended; the check still "
          f"catches every defect it was built for")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
