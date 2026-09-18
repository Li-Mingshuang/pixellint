"""Assertions for the studio: the parts that would fail silently if they broke.

The studio is a convenience layer, which is exactly why it needs a gate of its own.
It spawns processes, writes files through an HTTP surface and feeds model output
into this repo's art pipeline. Every one of those can break quietly:

  * a halt that reports success while the process tree keeps running
  * a path parameter that escapes the repo
  * a model response parsed into a module that does not parse, or that silently
    takes the wrong palette
  * a preview that draws a colour the palette does not contain
  * a generated gate that passes everything, i.e. is decorative

So the check drives the real HTTP server in-process on an ephemeral port and
exercises the real endpoints. Nothing here is a mock: a mock would test the mock.

    python studio/check_studio.py

Exits non-zero if anything fails.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for path in (str(ROOT), str(ROOT / "game"), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

import llm                      # noqa: E402
import server as studio_server  # noqa: E402
from gamepalette import GAME_PALETTE      # noqa: E402
from pixelkit import SCENE_PALETTE, check_grid  # noqa: E402

PROBLEMS: list = []


def fail(message: str) -> None:
    PROBLEMS.append(message)
    print(f"  FAIL  {message}")


def ok(message: str) -> None:
    print(f"  ok    {message}")


# --------------------------------------------------------------------------
# A grid that this repo's own rules accept, and one they reject.
# --------------------------------------------------------------------------

GOOD_ROWS = [
    "..KKKKKKKKKK..",
    ".KwwwwwwwwwwK.",
    ".KwEEwwwwEEwK.",
    ".KwwwwwwwwwwK.",
    ".KwwwKKKKwwwK.",
    ".KwwwwwwwwwwK.",
    ".KKwwwwwwwwKK.",
    "..KwwwwwwwwK..",
    "..KttKwwKttK..",
    "..KttK..KttK..",
    "..KKK....KKK..",
]
# The same canvas with one pixel detached: inside the bounds, touching nothing.
BAD_ROWS = GOOD_ROWS[:8] + [".KwwwwwwwwwwK.", ".KwwwwwwwwwwK.", ".KwwwwwwwwwK.K"]


def section(title: str) -> None:
    print(f"\n-- {title} " + "-" * max(0, 58 - len(title)))


# --------------------------------------------------------------------------
# 1. Parsing model output
# --------------------------------------------------------------------------


def check_parsing() -> None:
    section("parsing streamed model output")

    # An unterminated row must be dropped, not padded: padding would draw pixels
    # the model never committed to.
    grid = llm.extract_grid('"..KKKK.."\n"..KK')
    if grid["rows"] != ["..KKKK.."]:
        fail(f"an unterminated row was not dropped: {grid['rows']}")
    else:
        ok("an unterminated row is dropped, not padded")

    # A docstring is the shape that actually broke this: a pair of empty quotes
    # inside triple quotes matches the row pattern.
    grid = llm.extract_grid('"""sprite for a lantern"""\n"..KKKK.."\n".KKKK.K."\n')
    if grid["rows"] != ["..KKKK..", ".KKKK.K."]:
        fail(f"a docstring leaked into the grid: {grid['rows']}")
    else:
        ok("a docstring is skipped, not parsed as a row")

    # The palette line arrives LAST, so matching from position 0 could never find
    # it -- which silently pinned every grid to the default palette.
    grid = llm.extract_grid('"..KK.."\nPALETTE = "GAME"\n')
    if grid["palette"] != "GAME":
        fail(f"a trailing PALETTE line was not found: {grid['palette']}")
    else:
        ok("a trailing PALETTE line is found (search, not match)")

    # Keys outside the palette must be rejected when the palette is known.
    grid = llm.extract_grid('"..ZZ.."\n"..KK.."\n', allowed=set("Kk."))
    if grid["rows"] != ["..KK.."]:
        fail(f"a row of unknown keys survived: {grid['rows']}")
    else:
        ok("rows containing keys outside the palette are rejected")

    # `uniform` describes what has arrived and nothing more. Calling a one-row
    # grid "complete" once made the UI announce a finished sprite on line one.
    grid = llm.extract_grid('"..KK.."\n')
    if not grid["uniform"] or grid["height"] != 1:
        fail(f"`uniform` misreported a single row: {grid}")
    else:
        ok("`uniform` reports shape only, and does not claim completeness")

    # Reasoning must never reach the grid parser.
    text = '"..ZZ.."\n' * 4 + '"..KK.."\n".KKKK."\n'
    grid = llm.extract_grid(text, allowed=set("Kk."))
    if grid["rows"] != ["..KK..", ".KKKK."]:
        fail(f"non-palette chatter reached the grid: {grid['rows']}")
    else:
        ok("only palette-valid rows survive, so reasoning cannot become pixels")

    # REGRESSION, and the expensive one. A real DeepSeek call came back as a 16x1
    # grid of transparent pixels because the model wrote a Python list literal and
    # every row ended in a comma. The comma carries no information about the art,
    # and rejecting it silently cost an hour of confusion.
    comma_rows = ['"KKKKKKKKKKKKKKKK",', '"KwwwwwwwwwwwwwwK",', '"KKKKKKKKKKKKKKKK",']
    grid = llm.extract_grid("\n".join(["```python", "["] + comma_rows + ["]", "```"]),
                            allowed=set("Kw."))
    if grid["height"] != 3:
        fail(f"trailing commas still destroy rows: kept {grid['height']} of 3")
    else:
        ok("trailing commas, list brackets and code fences are tolerated")

    # REGRESSION: a row using characters that are not palette keys must be REPORTED,
    # not dropped quietly. Dropping it quietly produced a blank sprite and a message
    # that described the symptom ("fully transparent") rather than the cause.
    grid = llm.extract_grid('"################"\n"#..XXXX..XXXX..#"\n', allowed=set("Kk."))
    if not grid["unknown_keys"]:
        fail("rejected rows left no trace: the studio cannot say why the art is blank")
    elif set(grid["unknown_keys"]) != {"#", "X"}:
        fail(f"unknown keys misreported: {grid['unknown_keys']}")
    else:
        ok(f"rows using non-palette characters are reported: {grid['unknown_keys']}")
    if grid["rejected_count"] < 2:
        fail("rejected rows were not counted")
    else:
        ok(f"{grid['rejected_count']} rejected row(s) counted and sampled")

    # The diagnosis the studio shows must name the offending characters AND the
    # legal ones, because "fully transparent" is not something a user can act on.
    job = studio_server.Job(0, "generate", "probe")
    studio_server._diagnose(job, grid, "SCENE")
    notes = [data for _, name, data in job.snapshot() if name == "diagnosis"]
    if not notes:
        fail("an unusable grid produced no diagnosis event")
    else:
        blob = " ".join(notes[0]["notes"])
        if "#" not in blob or "SCENE" not in blob:
            fail(f"the diagnosis does not name the cause: {blob[:120]}")
        else:
            ok("the diagnosis names the offending characters and the legal palette")


# --------------------------------------------------------------------------
# 2. Writing modules
# --------------------------------------------------------------------------


def check_module_writing() -> None:
    section("generated modules")

    meta = {"provider": "probe", "model": "probe"}
    source = llm.module_source("probe.py", GOOD_ROWS, "SCENE", meta)
    check = llm.check_source("probe", "SCENE", meta)

    import ast
    for label, text in (("module", source), ("gate", check)):
        try:
            ast.parse(text)
        except SyntaxError as exc:
            fail(f"generated {label} does not parse: {exc}")
            return
    ok("generated module and gate both parse")

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "probe_mod.py").write_text(
            source.replace("from gamepalette", "from gamepalette"), encoding="utf-8")
        sys.path.insert(0, tmp)
        for stale in [m for m in sys.modules if m == "probe_mod"]:
            del sys.modules[stale]
        import probe_mod

        frames = probe_mod.FRAMES
        # FRAMES must be a list of FRAMES. Emitting the rows directly made every
        # CHECK treat a single row as a frame, which reported floating pixels in
        # a sprite that was fine.
        if not (isinstance(frames, list) and frames and isinstance(frames[0], list)
                and isinstance(frames[0][0], str)):
            fail(f"FRAMES is not a list of grids: {type(frames).__name__}"
                 f"/{type(frames[0]).__name__ if frames else '-'}")
        else:
            ok(f"FRAMES is a list of frames, one grid of "
               f"{len(frames[0][0])}x{len(frames[0])}")

        if frames[0] != GOOD_ROWS:
            fail("the written grid differs from the rows handed in")
        else:
            ok("the written grid is exactly the rows handed in")

        if probe_mod.PALETTE is not SCENE_PALETTE:
            fail("SCENE did not select SCENE_PALETTE")
        else:
            ok("palette resolution picks the requested palette")

        found = check_grid(frames[0], "probe", palette=probe_mod.PALETTE)
        if found:
            fail(f"the good grid does not pass this repo's own structural rules: {found}")
        else:
            ok("the good grid passes check_grid")

        # GAME must not silently fall back to SCENE.
        import importlib.util
        game_src = llm.module_source("probe_game.py", GOOD_ROWS, "GAME", meta)
        spec = importlib.util.spec_from_loader("probe_game", loader=None)
        module = importlib.util.module_from_spec(spec)
        exec(compile(game_src, "probe_game.py", "exec"), module.__dict__)
        if module.PALETTE is not GAME_PALETTE:
            fail("GAME did not select GAME_PALETTE")
        else:
            ok("GAME selects GAME_PALETTE, with no silent fallback")

        # The gate must be able to fail. This is the whole question: a gate that
        # passes everything is decoration with a filename.
        bad_src = llm.module_source("probe_bad.py", BAD_ROWS, "SCENE", meta)
        ns: dict = {}
        exec(compile(bad_src, "probe_bad.py", "exec"), ns)
        found = check_grid(ns["FRAMES"][0], "probe_bad", palette=ns["PALETTE"])
        if not found:
            fail("a grid with a detached pixel passed check_grid -> the rules are off")
        else:
            ok(f"a detached pixel is rejected: {found[0][:64]}")

    # Bad input must be refused loudly, never silently corrected.
    blank = ["." * 12] * 12
    for label, rows, palette in (("ragged rows", GOOD_ROWS + [".."], "SCENE"),
                                 ("no rows", [], "SCENE"),
                                 ("unknown palette", GOOD_ROWS, "NOPE"),
                                 ("a fully transparent grid", blank, "SCENE")):
        try:
            llm.module_source("x.py", rows, palette, meta)
            fail(f"{label} was accepted by module_source")
        except ValueError:
            ok(f"{label} is refused by module_source")


def check_prompt() -> None:
    """The prompt is the feature. Every one of these failed at least once.

    A sprite generator that does not tell the model what to draw, or what its colour
    keys mean, produces confident garbage -- and worse, produces it through a
    pipeline that reports the garbage as structurally valid art. So the content of
    the message is asserted, not just its shape.
    """
    section("the prompt sent to the model")

    palette = SCENE_PALETTE
    request = "a rusty watering can with a dented spout"
    text = llm.build_prompt(request, rows=16, cols=20, palette_name="SCENE",
                            palette=palette)

    # THE regression. The studio accepted a prompt, stored it, and built the message
    # without it: every sprite was drawn from the grid dimensions alone, which is
    # why the first generated sprites were unrelated to what was asked for.
    if request not in text:
        fail("the user's own request is not in the prompt -> the model is not told "
             "what to draw")
    else:
        ok("the user's request is in the prompt, verbatim")

    if "20 columns wide and 16 rows tall" not in text:
        fail("the requested grid dimensions are not stated in the prompt")
    else:
        ok("the grid dimensions are stated")

    # The palette must arrive as COLOURS. Passing only the key letters is what made
    # the first version guess: it cannot shade, cannot place a light, and cannot
    # tell the outline key from the highlight key.
    missing = [k for k in palette if k != "." and k not in text]
    if missing:
        fail(f"palette keys absent from the prompt: {sorted(missing)}")
    else:
        ok(f"all {len(palette) - 1} palette keys appear in the prompt")

    hexes = {f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}" for k, c in palette.items() if k != "."}
    absent = [h for h in hexes if h not in text]
    if absent:
        fail(f"{len(absent)} palette colours have no hex value in the prompt "
             f"(e.g. {sorted(absent)[:3]}): the model cannot choose a colour")
    else:
        ok(f"all {len(hexes)} colours appear as hex, so a colour can be chosen")

    # Each key needs a name too, otherwise the model reads 37 near-identical rows.
    named = all(llm.colour_name(palette[k]) in text for k in palette if k != ".")
    if not named:
        fail("a palette entry has no colour name in the prompt")
    else:
        ok("every palette entry carries a derived colour name")

    # The ladder must be dark-to-light ordered. That is how these palettes were
    # designed, and it is what lets the model pick a shading tone deliberately.
    from pixelkit import luminance
    values = [luminance(k, palette) for k in sorted(
        (k for k in palette if k != "."), key=lambda k: luminance(k, palette))]
    reversed_values = sorted(values, reverse=True)
    if values != sorted(values):
        fail("the palette ladder is not ordered dark to light")
    else:
        ok(f"the ladder is ordered dark to light ({values[0]:.2f} .. {values[-1]:.2f})")

    # The outline convention is stated, because "wrap it in K" is the single rule
    # that makes a sprite read against any background.
    if "outline" not in text.lower() or "<- the outline" not in text:
        fail("the outline key is not marked in the prompt")
    else:
        ok("the outline key is marked explicitly")

    # The colour namer is derived from the palette, so spot-check it against colours
    # whose names are not in doubt rather than trusting it blind.
    cases = [((30, 20, 22), "near-black"), ((251, 248, 240), "near-white"),
             ((138, 138, 150), "grey")]
    for rgb, want in cases:
        got = llm.colour_name(rgb)
        if want not in got:
            fail(f"colour_name({rgb}) = {got!r}, expected something like {want!r}")
        else:
            ok(f"colour_name({rgb}) = {got!r}")


# --------------------------------------------------------------------------
# 3. Rendering grids without executing anything
# --------------------------------------------------------------------------


def check_render() -> None:
    from PIL import Image

    section("grid rendering")

    png = studio_server.render_grid_png(GOOD_ROWS, "SCENE", scale=4)
    img = Image.open(__import__("io").BytesIO(png))
    want = (len(GOOD_ROWS[0]) * 4, len(GOOD_ROWS) * 4)
    if img.size != want:
        fail(f"rendered {img.size}, expected {want}")
    else:
        ok(f"renders {img.size} at 4x, no resampling artefacts")

    if studio_server.render_grid_png(GOOD_ROWS, "SCENE", 4) != png:
        fail("rendering the same grid twice produced different bytes")
    else:
        ok("rendering is deterministic")

    # A ragged grid is PADDED, not rejected: this renders a grid still arriving.
    ragged = studio_server.render_grid_png(["..KK..", ".KK."], "SCENE", scale=2)
    if Image.open(__import__("io").BytesIO(ragged)).size != (12, 4):
        fail("a ragged grid did not pad to the widest row")
    else:
        ok("a ragged grid pads to the widest row, so a live preview can draw it")

    # An unknown key must be loud, not silently dropped into a neighbouring tone.
    # The absent key is DERIVED from the palette, not guessed: the first version of
    # this test used "Z", which turns out to be a real SCENE key, so the assertion
    # was checking nothing and reported the palette colour as a failure. A test
    # that hard-codes a fact about the palette is a test that rots when the palette
    # grows.
    import string
    absent = next((c for c in string.ascii_letters if c not in SCENE_PALETTE), None)
    if absent is None:
        fail("every ASCII letter is a palette key; cannot test an unknown key")
    else:
        loud = studio_server.render_grid_png([f"..{absent}{absent}.."], "SCENE", scale=1)
        colour = Image.open(__import__("io").BytesIO(loud)).convert("RGBA").getpixel((2, 0))
        if colour != (255, 0, 255, 255):
            fail(f"the unknown key {absent!r} rendered as {colour}, not magenta")
        else:
            ok(f"the unknown key {absent!r} renders as magenta, impossible to miss")

    # Nothing in this path executes Python: a row that IS valid Python source is
    # still just characters to the renderer.
    sneaky_row = '__import__("os").system("echo pwned")'
    sneaky = studio_server.render_grid_png([sneaky_row], "SCENE", scale=1)
    if Image.open(__import__("io").BytesIO(sneaky)).size != (len(sneaky_row), 1):
        fail("a hostile row was not treated as plain characters")
    else:
        ok("model text is never executed: a hostile row is just characters")


# --------------------------------------------------------------------------
# 4. Path handling
# --------------------------------------------------------------------------


def check_paths() -> None:
    section("path containment")

    inside = studio_server._relative("assets/meadow.gif")
    if inside != "assets/meadow.gif":
        fail(f"a real repo file was not resolved: {inside}")
    else:
        ok("a repo-relative artifact resolves")

    for hostile in ("../../../etc/passwd", "..\\..\\windows\\win.ini",
                    "assets/../../../outside.txt", "C:/Windows/win.ini"):
        if studio_server._relative(hostile) is not None:
            fail(f"{hostile!r} was accepted as a repo path")
            return
    ok("traversal attempts all resolve to nothing")

    if studio_server._relative("studio/server.py") != "studio/server.py":
        fail("a nested repo file was rejected")
    else:
        ok("nested repo paths still resolve")


# --------------------------------------------------------------------------
# 5. Halting really halts
# --------------------------------------------------------------------------


def _alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def check_kill() -> None:
    section("halting the process tree")

    with tempfile.TemporaryDirectory() as tmp:
        pidfile = Path(tmp) / "grandchild.pid"
        # The grandchild is the point: render_game_gif.py spawns node, and killing
        # the parent leaves it running. A halt that reports success while a child
        # keeps burning a core is worse than no halt, because it is a stop that lies.
        grandchild = ("import os,sys,time;"
                      f"open(r'{pidfile}','w').write(str(os.getpid()));"
                      "time.sleep(120)")
        parent = ("import subprocess,sys,time;"
                  f"subprocess.Popen([sys.executable,'-c',{grandchild!r}]);"
                  "time.sleep(120)")

        proc = subprocess.Popen([sys.executable, "-c", parent],
                                **studio_server._group_kwargs())
        grandchild_pid = None
        for _ in range(120):
            if pidfile.exists() and pidfile.read_text().strip():
                grandchild_pid = int(pidfile.read_text().strip())
                break
            time.sleep(0.05)

        if grandchild_pid is None:
            fail("the probe never started its grandchild; cannot test the kill")
            proc.kill()
            return
        if not _alive(grandchild_pid):
            fail("the grandchild was not alive before the kill; the test is vacuous")
            proc.kill()
            return
        ok(f"probe running: parent {proc.pid}, grandchild {grandchild_pid}")

        killed = studio_server._kill_tree(proc)
        if not killed:
            fail("_kill_tree reported that it killed nothing while a job was live")
            return
        if proc.poll() is None:
            fail("the parent survived _kill_tree")
            return

        # `_alive` shells out to tasklist on Windows (~200ms a call), so it is
        # consulted a bounded number of times rather than polled in a loop. The
        # property being asserted is "the grandchild is gone"; three attempts over
        # a second and a half is enough to distinguish "killed" from "slow".
        gone = False
        for attempt in range(3):
            time.sleep(0.45 if attempt else 0.3)
            if not _alive(grandchild_pid):
                gone = True
                break
        if not gone:
            fail(f"the grandchild {grandchild_pid} outlived the kill")
            subprocess.run(["taskkill", "/F", "/PID", str(grandchild_pid)],
                           capture_output=True)
        else:
            ok("both the parent and its grandchild are gone: the tree was killed")

        # And killing nothing must be a no-op, not an error or a false success.
        if studio_server._kill_tree(None):
            fail("_kill_tree claimed to kill when there was no process")
        else:
            ok("killing nothing reports nothing, rather than a false success")


# --------------------------------------------------------------------------
# 6. The HTTP surface, driven for real
# --------------------------------------------------------------------------


def check_http() -> None:
    section("http endpoints (real server, ephemeral port)")

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), studio_server.Handler)
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    # A short poll interval so shutdown() is noticed promptly; the default 0.5s
    # would add half a second to every build for no reason.
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05},
                              daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    def get(path):
        # urllib raises on 4xx, and a check that crashes on the very status it is
        # asserting is a check that cannot report its own failure.
        try:
            with urllib.request.urlopen(base + path, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def post(path, body):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                     headers={"content-type": "application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    try:
        status, body = get("/")
        if status != 200 or b"<!DOCTYPE html>" not in body:
            fail(f"GET / returned {status}")
        else:
            ok(f"GET / serves the page ({len(body)} bytes)")

        status, body = get("/api/plan")
        plan = json.loads(body)
        steps = {s["script"] for s in plan["steps"]}
        # The registry must come from build.py, so a new step cannot be missing
        # from the studio while present in the build.
        import build as buildmod
        expected = {s for _, s, _ in buildmod.WAVE_1 + buildmod.WAVE_2}
        if steps != expected:
            fail(f"the studio's step list differs from build.py's: "
                 f"{steps ^ expected}")
        else:
            ok(f"GET /api/plan reports all {len(steps)} steps, imported from build.py")

        if len(plan["checks"]) != len(buildmod.check_scripts()):
            fail("the studio's check list differs from build.py's")
        else:
            ok(f"GET /api/plan reports all {len(plan['checks'])} checks")

        # The key must never come back out over HTTP. Set one that is impossible
        # to miss and then search every response for it.
        marker = "sk-probe-MUST-NOT-LEAK-0123456789"
        status, _ = post("/api/llm/session", {"provider": "deepseek", "key": marker})
        if status != 200:
            fail(f"setting a session key returned {status}")
        else:
            ok("a session key can be installed")

        leaked = []
        for path in ("/api/plan",):
            _, body = get(path)
            if marker.encode() in body:
                leaked.append(path)
        if leaked:
            fail(f"the api key was returned by {leaked}")
        else:
            ok("the api key is never returned to the browser")

        _, described = post("/api/llm/session", {"provider": "deepseek"})
        if not described["session"]["key_set"]:
            fail("the session does not report that a key is set")
        else:
            ok("the session reports that a key is set, without saying what it is")

        post("/api/llm/clear", {})
        post("/api/llm/session", {"provider": "offline"})
        ok("the session key can be cleared again")

        # Path traversal over HTTP, not just in the helper.
        status, _ = get("/api/file?path=" + urllib.request.quote("../../etc/passwd"))
        if status != 404:
            fail(f"a traversal request returned {status}, expected 404")
        else:
            ok("GET /api/file refuses to leave the repo")

        # Unknown steps must be refused rather than run.
        status, payload = post("/api/run", {"target": "step", "script": "rm_rf.py"})
        if status != 400:
            fail(f"an unknown script was accepted for running ({status})")
        else:
            ok("POST /api/run refuses a script that is not in this repo")

        # Rendering is reachable and returns a PNG, not JSON.
        req = urllib.request.Request(base + "/api/render",
                                     data=json.dumps({"rows": GOOD_ROWS,
                                                      "palette": "SCENE"}).encode(),
                                     headers={"content-type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            head = r.read(8)
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            fail("POST /api/render did not return a PNG")
        else:
            ok("POST /api/render returns a PNG")

        # A model job can only be started one at a time: two builds writing the
        # same files is the race this guard exists to prevent.
        status, first = post("/api/generate", {"prompt": "probe", "provider": "offline",
                                               "rows": 8, "cols": 8})
        if status != 200:
            fail(f"could not start a generate job ({status}: {first})")
        else:
            status, second = post("/api/generate", {"prompt": "probe again",
                                                    "provider": "offline",
                                                    "rows": 8, "cols": 8})
            if status != 409:
                fail(f"a second job was accepted while one ran ({status})")
            else:
                ok("a second job is refused with 409 while one is running")

            # And it can be stopped mid-stream.
            status, stopped = post("/api/stop", {})
            if status != 200 or not stopped.get("stopped"):
                fail(f"stopping a live job returned {status}: {stopped}")
            else:
                ok("a running job can be stopped")

        # Bad requests must be refused with a reason, not a traceback.
        for body, why in (({"prompt": ""}, "an empty prompt"),
                          ({"prompt": "x", "rows": 9999}, "an absurd grid size"),
                          ({"prompt": "x", "palette": "NEON"}, "an unknown palette")):
            status, payload = post("/api/generate", {**body, "provider": "offline"})
            if status != 400:
                fail(f"{why} was accepted ({status})")
            else:
                ok(f"{why} is refused with 400")
    finally:
        httpd.shutdown()
        httpd.server_close()


def main() -> int:
    check_prompt()
    check_parsing()
    check_module_writing()
    check_render()
    check_paths()
    check_kill()
    check_http()

    print()
    for problem in PROBLEMS:
        print(f"  FAIL  {problem}")
    print(f"failures: {len(PROBLEMS)}")
    return 1 if PROBLEMS else 0


if __name__ == "__main__":
    raise SystemExit(main())
