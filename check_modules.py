"""Assert that importing a module is safe, because evaluate.py depends on it.

evaluate.py discovers assets by SHAPE: it imports every non-underscore,
non-`check_`, non-internal module in the repo root and in game/ and looks for
exported blocks. That is a good design -- a new sprite module is measured the
moment it is written, with nothing to register. It rests on an invariant stated
in a comment beside the discovery code:

    "Importing is safe: every module here guards its entry point behind
     `if __name__ == \"__main__\"`, so importing one only defines names."

A comment cannot enforce that. During a build-optimisation pass, six throwaway
measurement scripts were dropped into the repo root. They had no `__main__`
guard, so the report step imported them -- and they ran. They printed their
benchmarks into the middle of the build output, one of them called sys.exit(),
and the build went from 8.4 s to 17.9 s with no failing step to point at the
cause. Nothing was broken; the assumption had simply stopped being true, and
nothing was watching it.

So it is watched now, behaviourally rather than syntactically: each module is
imported in a subprocess with its output captured, and any module that talks,
exits or throws is named. Import-time work that is silent and pure -- building
grids, deriving a palette -- is fine and is not flagged.

The probe deliberately reuses evaluate.py's own candidate list instead of
restating the rule, so the two cannot drift apart.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

PROBE = r'''
import contextlib, importlib, io, json, sys

names = json.loads(sys.argv[1])
bad = {}
for name in names:
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            importlib.import_module(name)
    except SystemExit as exc:
        bad[name] = f"calls sys.exit({exc.code!r}) at import time"
        continue
    except BaseException as exc:                       # noqa: BLE001 - reporting
        bad[name] = f"raises {type(exc).__name__} at import: {exc}"
        continue
    noise = buf.getvalue().strip()
    if noise:
        head = noise.splitlines()[0][:64]
        bad[name] = f"writes to stdout at import: {head!r}"
print("@@RESULT@@" + json.dumps(bad))
'''


def probe(names, extra_path=None):
    """Import `names` in a clean subprocess; return {name: complaint}."""
    import os
    env = dict(os.environ)
    if extra_path:
        env["PYTHONPATH"] = str(extra_path) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run([sys.executable, "-c", PROBE, json.dumps(names)],
                          cwd=HERE, capture_output=True, text=True, env=env)
    for line in proc.stdout.splitlines():
        if line.startswith("@@RESULT@@"):
            return json.loads(line[len("@@RESULT@@"):])
    print(proc.stdout)
    print(proc.stderr)
    raise SystemExit("probe produced no result")


def candidates():
    """evaluate.py's own list. Imported, not copied, so they cannot drift."""
    sys.path.insert(0, str(HERE))
    import evaluate

    return [name for _, name in evaluate._candidate_modules()]


def main() -> int:
    names = candidates()
    print(f"-- modules importable by evaluate.py ({len(names)}) " + "-" * 12)
    print(f"  {', '.join(names)}")

    bad = probe(names)
    for name in names:
        if name in bad:
            print(f"  FAIL  {name}: {bad[name]}")
    if not bad:
        print(f"  ok    all {len(names)} import silently and only define names")

    # -- negative test ------------------------------------------------------
    # The assertion above is only worth having if it can fail. So build a module
    # that violates the invariant in exactly the way the throwaway scripts did,
    # in a temp directory that the build's discovery cannot see.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "noisy_probe_module.py").write_text(
            "print('I ran during an import')\nVALUE = 1\n", encoding="utf-8")
        (tmp_path / "exiting_probe_module.py").write_text(
            "import sys\nsys.exit(3)\n", encoding="utf-8")
        caught = probe(["noisy_probe_module", "exiting_probe_module"], extra_path=tmp_path)

    ok = "noisy_probe_module" in caught and "exiting_probe_module" in caught
    print("\n-- negative test: is this check able to fail? ---------------")
    for name, why in sorted(caught.items()):
        print(f"  detected  {name}: {why}")
    if ok:
        print("  ok    a module that prints, and one that exits, are both caught")
    else:
        print("  FAIL  the check did not notice deliberately broken modules "
              "-> it is decorative")

    print()
    failures = len(bad) + (0 if ok else 1)
    print(f"failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
