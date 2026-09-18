"""The studio server: watch the pipeline run, halt it, change something, rerun.

Stdlib only. Run it with:

    python studio/server.py            # http://127.0.0.1:8777
    python studio/server.py --port 9000

WHAT THIS IS FOR
----------------
The pipeline's whole premise is that the model cannot see its own output, so every
claim about the art is an assertion plus a number. That leaves one gap: a human
looking at the result has no cheap way to watch the generation, stop it when it is
going wrong, or change something and see the effect without waiting for a full
build. This closes that gap. It adds no new checking -- it runs the same steps, the
same checks, and the same palettes, and shows you what they say as they say it.

DESIGN DECISIONS THAT MATTER
----------------------------
* **Only the loopback interface.** This server spawns processes and can write
  files. Binding it to 0.0.0.0 would put that on the network. It is not
  authenticated because it is not reachable.
* **One job at a time.** A build and a build are not independent -- they write the
  same files. A second request while one is running is refused rather than
  interleaved, so a half-stopped build cannot race a half-started one.
* **Process-TREE kill.** `render_game_gif.py` spawns node, and node is not killed
  by terminating its parent. Halt has to kill the group, or the studio leaves an
  orphan holding the CPU it was supposed to free.
* **An event replay buffer.** A client connects a moment after it asks for a run,
  and the first lines of output are already gone. Every event is kept, replayed on
  connect, then streamed live. Without this the log has a silent hole at the start,
  which is exactly where the errors are.
* **The step registry is imported, not restated.** Steps, their scripts and their
  declared outputs come from build.py. A second copy of that list in the studio
  would be a list to keep in sync, and this repo has already been bitten twice by
  those.
* **Model output is never executed.** The generate path parses text into rows and
  renders them through the same palette tables the art uses. See studio/llm.py.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# `game/` is on the path because its sprite modules are imported by stem, the way
# every check in this repo imports art.
for path in (str(ROOT), str(ROOT / "game"), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

import llm  # noqa: E402  (after sys.path setup)

DEFAULT_PORT = 8777
HOST = "127.0.0.1"

# How much of a run a late-connecting client can replay. Bounded because the
# buffer is per-job and a build emits a line per step plus an event per artifact.
MAX_REPLAY_EVENTS = 20000

# Lines a step writes that name a file it just produced. build steps already print
# these; the studio reads them rather than guessing what a step produces, so a new
# step's artifacts show up in the gallery with no registration anywhere.
_WROTE = re.compile(r"\bwrote\b\s*:?\s*(.+)$", re.IGNORECASE)
_ARTIFACT = re.compile(r"([\w./\\-]+\.(?:png|gif|js|json|md))\b", re.IGNORECASE)
# A failing assertion and a warning are the two things a human must see immediately.
_VERDICT = re.compile(r"^\s*(FAIL|WARN|note)\b(.*)$")


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------


class Job:
    """One running step, check, build or model call, with a replayable event log."""

    def __init__(self, job_id: int, kind: str, label: str):
        self.id = job_id
        self.kind = kind                 # "build" | "step" | "check" | "generate"
        self.label = label
        self.events: list = []           # (seq, event_name, data) for replay
        self.queue: queue.Queue = queue.Queue()
        self.lock = threading.Lock()
        self.stop_requested = threading.Event()
        self.done = threading.Event()
        self.rc: int | None = None
        self.proc: subprocess.Popen | None = None
        self.started = time.time()
        self.ended: float | None = None
        self._seq = 0
        self.text = ""                   # accumulated model output, for generate jobs

    # -- event plumbing ----------------------------------------------------
    def emit(self, name: str, data) -> None:
        with self.lock:
            self._seq += 1
            event = (self._seq, name, data)
            # The replay buffer is what a late-connecting client reads, so it has
            # to be bounded -- an unbounded one turns a chatty run into a memory
            # leak. Dropping the OLDEST is right: the end of a build is what you
            # are looking at, and the live queue still carries everything.
            self.events.append(event)
            if len(self.events) > MAX_REPLAY_EVENTS:
                del self.events[:len(self.events) - MAX_REPLAY_EVENTS]
            self.queue.put(event)

    def snapshot(self) -> list:
        with self.lock:
            return list(self.events)

    def status(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "label": self.label,
            "running": not self.done.is_set(), "rc": self.rc,
            "started": self.started, "ended": self.ended,
            "seconds": (self.ended or time.time()) - self.started,
        }


class Studio:
    """Owns the single running job and the session's model configuration."""

    def __init__(self):
        self.lock = threading.Lock()
        self.current: Job | None = None
        self.last: Job | None = None
        self._next_id = 0
        self.backups: dict = {}          # rel path -> original source text

    # -- lifecycle ---------------------------------------------------------
    def _claim(self, kind: str, label: str) -> Job:
        with self.lock:
            if self.current and not self.current.done.is_set():
                raise RuntimeError(
                    f"{self.current.label!r} is already running; stop it first")
            self._next_id += 1
            job = Job(self._next_id, kind, label)
            self.current = job
            return job

    def _finish(self, job: Job, rc: int) -> None:
        job.rc = rc
        job.ended = time.time()
        job.emit("done", {"rc": rc, "seconds": job.ended - job.started})
        job.done.set()
        with self.lock:
            self.last = job

    def stop(self) -> dict:
        with self.lock:
            job = self.current
        if job is None or job.done.is_set():
            return {"stopped": False, "reason": "nothing is running"}
        job.stop_requested.set()
        killed = _kill_tree(job.proc)
        job.emit("stopped", {"killed": killed})
        return {"stopped": True, "killed": killed, "job": job.id}

    # -- running a subprocess step ----------------------------------------
    def run_process(self, kind: str, label: str, argv: list) -> Job:
        job = self._claim(kind, label)
        thread = threading.Thread(target=self._pump_process, args=(job, argv),
                                  daemon=True)
        thread.start()
        return job

    def _pump_process(self, job: Job, argv: list) -> None:
        job.emit("start", {"label": job.label, "argv": argv,
                           "cwd": str(ROOT)})
        rc = 1
        try:
            proc = subprocess.Popen(
                argv, cwd=str(ROOT), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1,
                encoding="utf-8", errors="replace",
                **_group_kwargs(),
            )
            job.proc = proc
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip("\n")
                job.emit("line", {"text": line})
                self._inspect_line(job, line)
                if job.stop_requested.is_set():
                    break
            rc = proc.wait(timeout=30)
        except Exception as exc:                                  # noqa: BLE001
            job.emit("error", {"message": f"{type(exc).__name__}: {exc}",
                               "traceback": traceback.format_exc()[-1200:]})
        finally:
            job.proc = None
            self._finish(job, rc)

    def _inspect_line(self, job: Job, line: str) -> None:
        """Turn a step's own output into events, rather than predicting them."""
        verdict = _VERDICT.match(line)
        if verdict:
            kind, rest = verdict.group(1).lower(), verdict.group(2).strip()
            if kind == "note":
                kind = "warn"
            job.emit("verdict", {"level": kind, "text": rest or line.strip()})

        wrote = _WROTE.search(line)
        if wrote:
            for match in _ARTIFACT.finditer(wrote.group(1)):
                rel = _relative(match.group(1))
                if rel:
                    job.emit("asset", _asset_info(rel) or {"path": rel})

    # -- running a model call ---------------------------------------------
    def generate(self, prompt: str, cols: int, rows_hint: int, palette_name: str,
                 provider_name: str | None, model: str | None) -> Job:
        job = self._claim("generate", f"generate ({provider_name or 'auto'})")
        thread = threading.Thread(
            target=self._pump_generate,
            args=(job, prompt, cols, rows_hint, palette_name, provider_name, model),
            daemon=True)
        thread.start()
        return job

    def _pump_generate(self, job: Job, prompt: str, cols: int, rows_hint: int,
                       palette_name: str, provider_name: str | None,
                       model: str | None) -> None:
        rc = 1
        try:
            palette = _palette(palette_name)
            allowed = set(palette) | {"."}
            provider, chosen_model, key = llm.resolve(provider_name, model)
            job.emit("start", {
                "label": job.label, "provider": provider.name,
                "model": chosen_model, "kind": provider.kind,
                "base_url": provider.base_url,
                "key_present": bool(key),
                "offline": provider.kind == "offline",
            })
            messages = [
                {"role": "system", "content": llm.SYSTEM},
                # `prompt` is the user's own words. It MUST reach the model: the
                # first version accepted a prompt, stored it on the job, and built
                # the message without it, so every sprite was drawn from the grid
                # dimensions alone.
                {"role": "user", "content": llm.build_prompt(
                    prompt, rows_hint, cols, palette_name, palette)},
            ]
            # The grid event is throttled to the moments the picture can actually
            # change -- a new row, or a row whose width changed. Emitting the whole
            # grid on every token would put thousands of near-identical copies in
            # the replay buffer for a preview that redraws identically.
            last_shape = None
            finish_reason = None
            for channel, piece in llm.stream(messages, provider, chosen_model, key,
                                             job.stop_requested.is_set):
                if job.stop_requested.is_set():
                    break
                if channel == "finish":
                    finish_reason = piece
                    continue
                if channel == "content":
                    job.text += piece
                job.emit(channel, {"text": piece})
                if channel != "content":
                    continue
                grid = llm.extract_grid(job.text, allowed=allowed)
                shape = (grid["height"], tuple(grid["widths"]))
                if shape != last_shape:
                    last_shape = shape
                    job.emit("grid", grid)

            grid = llm.extract_grid(job.text, allowed=allowed)
            job.emit("grid", grid)
            # A truncated response quietly loses the bottom of the sprite. Nothing
            # else reports it: the rows that did arrive are perfectly valid, so the
            # grid looks short rather than broken.
            if finish_reason in ("length", "max_tokens"):
                job.emit("diagnosis", {"notes": [
                    f"the response hit the model's output limit and was cut off "
                    f"(finish_reason={finish_reason}); the sprite is missing its "
                    f"bottom rows. Try a smaller grid, or a model with a larger "
                    f"output limit."], "rows_kept": grid["height"],
                    "rows_rejected": grid.get("rejected_count", 0),
                    "palette_keys": ""})
            _diagnose(job, grid, palette_name)
            # The user chose the palette in the form, so that choice wins. The model
            # is no longer asked for a PALETTE line, and if it volunteers one it is
            # reported rather than obeyed -- silently switching palettes would mean
            # the colours in the preview are not the ones the user picked.
            if grid["palette"] and grid["palette"] != palette_name:
                job.emit("note", {"text":
                    f"the model asked for the {grid['palette']} palette; keeping "
                    f"{palette_name} as chosen in the form"})
            palette_final = palette_name
            meta = {"provider": provider.name, "model": chosen_model}
            try:
                source = llm.module_source("generated_sprite.py", grid["rows"],
                                          palette_final, meta)
                # The gate is generated WITH the art, not after it. Art that
                # arrives unverified is the one thing this repo exists to avoid.
                check = llm.check_source("generated_sprite", palette_final, meta)
                job.emit("source", {"python": source, "check": check, "grid": grid})
                rc = 0
            except ValueError as exc:
                job.emit("error", {"message": f"no module could be written: {exc}",
                                   "grid": grid})
                rc = 2
        except Exception as exc:                                  # noqa: BLE001
            job.emit("error", {"message": f"{type(exc).__name__}: {exc}",
                               "traceback": traceback.format_exc()[-1200:]})
        finally:
            self._finish(job, rc)


# --------------------------------------------------------------------------
# Process control
# --------------------------------------------------------------------------


def _group_kwargs() -> dict:
    """Start each step in its own process group so halt can kill the whole tree."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _kill_tree(proc: subprocess.Popen | None) -> bool:
    """Kill a step AND its children. Returns True if a kill was issued.

    Terminating the parent is not enough: `render_game_gif.py` runs node, and a
    killed parent leaves node running. The studio would then report "stopped"
    while a process it started kept burning a core -- which is worse than not
    stopping at all, because it is a stop that lies.
    """
    if proc is None or proc.poll() is not None:
        return False
    pid = proc.pid
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, check=False)
    else:
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            return False
        time.sleep(0.4)
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    return True


# --------------------------------------------------------------------------
# Repo introspection -- all of it imported from the modules that own it
# --------------------------------------------------------------------------


def _load_build():
    import build as buildmod
    return buildmod


def _relative(token: str) -> str | None:
    token = token.strip().strip('"\'').rstrip(".,")
    try:
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        resolved = candidate.resolve()
        resolved.relative_to(ROOT)
    except (ValueError, OSError):
        return None
    if not resolved.is_file():
        return None
    return resolved.relative_to(ROOT).as_posix()


def _asset_info(rel: str) -> dict | None:
    path = ROOT / rel
    try:
        stat = path.stat()
    except OSError:
        return None
    return {"path": rel, "size": stat.st_size, "mtime": stat.st_mtime,
            # a token the page appends to the URL so the browser cannot serve a
            # cached GIF. Browsers cache images aggressively and a stale preview is
            # indistinguishable from a change that did not happen.
            "v": int(stat.st_mtime * 1000)}


def list_assets() -> list:
    out = []
    for base in ("assets", "game"):
        directory = ROOT / base
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.suffix.lower() not in (".png", ".gif", ".jpg", ".webp"):
                continue
            rel = path.relative_to(ROOT).as_posix()
            info = _asset_info(rel)
            if info:
                out.append(info)
    out.sort(key=lambda a: a["mtime"], reverse=True)
    return out


def _palette(name: str):
    from gamepalette import GAME_PALETTE
    from pixelkit import SCENE_PALETTE
    return GAME_PALETTE if name == "GAME" else SCENE_PALETTE


def _diagnose(job: Job, grid: dict, palette_name: str) -> None:
    """Say WHY a generated grid is unusable, in terms of what the model did.

    This exists because of a real failure. A DeepSeek call came back as a 16x1 grid
    of transparent pixels, and all the studio could say was "fully transparent" --
    which is a description of the symptom, not the cause. The cause was that the
    model had written a Python list literal, so every row ended in a comma and the
    parser of the day rejected all of them, keeping one blank row that happened to
    end in a quote. An hour of confusion for a comma.

    So: never report an empty grid without saying what was thrown away and what
    characters were not palette keys. The user cannot fix what they cannot see.
    """
    stray = grid.get("unknown_keys") or {}
    reasons: dict = {}
    for reason, sample in grid.get("rejected") or []:
        reasons.setdefault(reason, sample)

    notes = []
    if grid["height"] == 0:
        notes.append("no usable rows arrived at all")
    if stray:
        shown = ", ".join(f"{ch!r} x{count}" for ch, count in list(stray.items())[:6])
        notes.append(f"characters that are not {palette_name} palette keys: {shown}")
    for reason, sample in list(reasons.items())[:4]:
        notes.append(f"rejected ({reason}): {sample}")
    if grid["height"] and not grid["opaque"]:
        notes.append(f"{grid['height']} row(s) arrived but every pixel is '.'")

    if notes:
        job.emit("diagnosis", {
            "notes": notes,
            "palette_keys": "".join(sorted(k for k in _palette(palette_name) if k != ".")),
            "rows_kept": grid["height"],
            "rows_rejected": grid.get("rejected_count", 0),
        })


def _palette_help(name: str) -> str:
    """Kept only for the plan endpoint's blurb. The prompt no longer uses it.

    It used to be passed to the model, and it was wrong for the job: it described
    SCENE as "objects are placed on a ground line and must not overlap another
    object while sharing a dominant colour" -- a rule about arranging a SCENE,
    handed to a model that had been asked to draw one sprite. Guidance that does
    not apply to the task is worse than no guidance.
    """
    return "meadow scene" if name != "GAME" else "side-scrolling shooter"


def plan() -> dict:
    """The step graph, with real freshness from build.py's own cache test."""
    buildmod = _load_build()
    steps = []
    for wave, entries in (("render", buildmod.WAVE_1),
                          ("render (dependent)", buildmod.WAVE_2)):
        for label, script, outputs in entries:
            steps.append({
                "label": label, "script": script, "outputs": outputs,
                "wave": wave,
                "fresh": bool(buildmod.is_fresh(script, outputs)),
            })
    checks = []
    for script in buildmod.check_scripts():
        checks.append({"script": script, "label": Path(script).stem, "wave": "verify"})
    return {
        "steps": steps,
        "checks": checks,
        "report": [{"label": label, "argv": argv}
                   for label, argv in buildmod.REPORT_STEPS],
        "llm": llm.describe(),
        "root": str(ROOT),
    }


def module_grids(name: str) -> dict:
    """Read a module's grids for the inspector. Imports the module, which is how
    every check in this repo reads art, so it is the same trust boundary."""
    import importlib
    stem = name[:-3] if name.endswith(".py") else name
    module = importlib.import_module(stem)

    frames = []
    for attr in ("FRAMES", "DOG_FRAMES", "SPRITE", "GROUND", "BACKDROP"):
        if not hasattr(module, attr):
            continue
        frames.extend(_as_frames(getattr(module, attr), attr))
    palette = getattr(module, "PALETTE", None)
    palette_name = "GAME" if getattr(module, "PALETTE_NAME", "") == "GAME" else "SCENE"
    return {"module": stem, "frames": frames, "palette": palette_name,
            "attrs": sorted(a for a in dir(module) if a.isupper())}


def _as_frames(value, attr: str, limit: int = 8) -> list:
    """Normalise the several shapes art takes in this repo into labelled grids."""
    out = []
    if not value:
        return out
    if isinstance(value, list) and value and isinstance(value[0], str):
        out.append({"label": attr, "rows": value})
    elif isinstance(value, list):
        for i, item in enumerate(value[:limit]):
            if isinstance(item, list) and item and isinstance(item[0], str):
                out.append({"label": f"{attr}[{i}]", "rows": item})
    elif isinstance(value, dict):
        for key, item in list(value.items())[:limit]:
            if isinstance(item, list) and item and isinstance(item[0], str):
                out.append({"label": f"{attr}[{key}]", "rows": item})
    return out


# --------------------------------------------------------------------------
# Rendering a grid to PNG -- no model output is ever executed
# --------------------------------------------------------------------------


def render_grid_png(rows: list, palette_name: str, scale: int = 6) -> bytes:
    """Draw rows of palette keys. Deterministic; text in, pixels out.

    Ragged rows are padded with transparency rather than rejected, because this
    renders a grid that is still arriving. Nothing here parses Python or executes
    anything from the model -- the keys are looked up in this repo's own palette
    table and an unknown key is drawn as magenta, which is loud on purpose: a
    colour that is not in the palette should be impossible to miss.
    """
    from PIL import Image

    palette = _palette(palette_name)
    width = max((len(r) for r in rows), default=0)
    height = len(rows)
    if not width or not height:
        raise ValueError("nothing to draw")
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = img.load()
    missing = set()
    for y, row in enumerate(rows):
        for x, key in enumerate(row):
            if key == ".":
                continue
            colour = palette.get(key)
            if colour is None:
                missing.add(key)
                colour = (255, 0, 255, 255)
            px[x, y] = colour
    out = img.resize((width * scale, height * scale),
                     Image.Resampling.NEAREST)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

STUDIO = Studio()
UI_PATH = HERE / "ui.html"


class Handler(BaseHTTPRequestHandler):
    server_version = "pixellint-studio"
    protocol_version = "HTTP/1.0"      # SSE is close-delimited; no chunking needed

    def log_message(self, fmt, *args):      # quieter, and no per-asset spam
        if self.path.startswith("/api/events"):
            return
        sys.stderr.write(f"  {self.command} {self.path}  {fmt % args}\n")

    # -- helpers -----------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    def _json(self, payload, code: int = 200):
        self._send(code, json.dumps(payload).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, message: str, code: int = 400):
        self._json({"error": message}, code)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"body is not JSON: {exc}") from exc

    # -- routes ------------------------------------------------------------
    def do_GET(self):                                       # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        route = parsed.path
        try:
            if route in ("/", "/index.html"):
                return self._send(200, UI_PATH.read_bytes(),
                                  "text/html; charset=utf-8")
            if route == "/api/plan":
                return self._json(plan())
            if route == "/api/assets":
                return self._json({"assets": list_assets()})
            if route == "/api/current":
                job = STUDIO.current
                return self._json({
                    "job": job.status() if job else None,
                    "last": STUDIO.last.status() if STUDIO.last else None,
                })
            if route == "/api/module":
                name = (query.get("name") or [""])[0]
                rel = _relative(name)
                if not rel or not rel.endswith(".py"):
                    return self._error("not a module in this repo")
                return self._json({
                    "name": rel,
                    "source": (ROOT / rel).read_text(encoding="utf-8"),
                    "dirty": rel in STUDIO.backups,
                })
            if route == "/api/grid":
                name = (query.get("name") or [""])[0]
                try:
                    return self._json(module_grids(name))
                except Exception as exc:                      # noqa: BLE001
                    return self._error(f"{type(exc).__name__}: {exc}")
            if route == "/api/file":
                rel = _relative((query.get("path") or [""])[0])
                if not rel:
                    return self._error("no such file", 404)
                ctype = ("image/gif" if rel.endswith(".gif")
                         else "image/png" if rel.endswith(".png")
                         else "text/javascript" if rel.endswith(".js")
                         else "application/octet-stream")
                return self._send(200, (ROOT / rel).read_bytes(), ctype)
            if route == "/api/events":
                return self._stream(int((query.get("job") or ["0"])[0]))
            return self._error("no such route", 404)
        except ValueError as exc:
            return self._error(str(exc))
        except Exception as exc:                              # noqa: BLE001
            return self._error(f"{type(exc).__name__}: {exc}", 500)

    def do_POST(self):                                      # noqa: N802
        route = urlparse(self.path).path
        try:
            payload = self._body()
        except ValueError as exc:
            return self._error(str(exc))

        try:
            if route == "/api/run":
                return self._run(payload)
            if route == "/api/stop":
                return self._json(STUDIO.stop())
            if route == "/api/llm/session":
                llm.set_session(provider=payload.get("provider"),
                                model=payload.get("model"),
                                base_url=payload.get("base_url"),
                                key=payload.get("key"))
                return self._json(llm.describe())
            if route == "/api/llm/clear":
                llm.clear_session()
                return self._json(llm.describe())
            if route == "/api/generate":
                return self._generate(payload)
            if route == "/api/render":
                rows = payload.get("rows") or []
                png = render_grid_png(rows, payload.get("palette") or "SCENE",
                                      scale=int(payload.get("scale") or 6))
                return self._send(200, png, "image/png")
            if route == "/api/write":
                return self._write(payload)
            if route == "/api/revert":
                return self._revert(payload)
            return self._error("no such route", 404)
        except RuntimeError as exc:
            return self._error(str(exc), 409)
        except ValueError as exc:
            return self._error(str(exc))
        except Exception as exc:                              # noqa: BLE001
            return self._error(f"{type(exc).__name__}: {exc}", 500)

    # -- route implementations --------------------------------------------
    def _run(self, payload: dict):
        target = payload.get("target") or "build"
        force = bool(payload.get("force"))
        python = sys.executable

        if target == "build":
            argv = [python, "build.py"] + (["--force"] if force else [])
            job = STUDIO.run_process("build", "build.py", argv)
            return self._json({"job": job.id, "argv": argv})

        buildmod = _load_build()
        script = payload.get("script") or ""
        known = {s for _, s, _ in buildmod.WAVE_1 + buildmod.WAVE_2}
        known |= set(buildmod.check_scripts())
        # A module the studio just generated is not in the step registry -- it has
        # no declared outputs and no wave -- but running it is the whole point of
        # writing it. Any .py inside this repo may be run, which is the same trust
        # boundary as /api/write (both are loopback-only and both already run
        # build.py, which runs everything anyway).
        rel = _relative(script)
        if script not in known:
            if not (rel and rel.endswith(".py")):
                return self._error(f"{script!r} is not a step in this pipeline")

        kind = "check" if Path(script).stem.startswith("check_") else "step"
        argv = [python, script]
        if payload.get("args"):
            argv.extend(str(a) for a in payload["args"])
        job = STUDIO.run_process(kind, script, argv)
        return self._json({"job": job.id, "argv": argv})

    def _generate(self, payload: dict):
        prompt = (payload.get("prompt") or "").strip()
        if not prompt:
            return self._error("a prompt is required")
        rows = int(payload.get("rows") or 16)
        cols = int(payload.get("cols") or 16)
        if not (2 <= rows <= 128 and 2 <= cols <= 128):
            return self._error("rows and cols must be between 2 and 128")
        palette = (payload.get("palette") or "SCENE").upper()
        if palette not in ("SCENE", "GAME"):
            return self._error("palette must be SCENE or GAME")
        job = STUDIO.generate(prompt, cols, rows, palette,
                             payload.get("provider"), payload.get("model"))
        return self._json({"job": job.id})

    def _write(self, payload: dict):
        rel = (payload.get("path") or "").strip()
        source = payload.get("source")
        if not rel.endswith(".py") or not source:
            return self._error("path must be a .py file and source must be present")
        if "/" in rel or "\\" in rel:
            return self._error("write to the repo root only, by bare filename")
        target = (ROOT / rel).resolve()
        try:
            target.relative_to(ROOT)
        except ValueError:
            return self._error("outside the repo")

        written = []
        items = [(rel, source)]
        # The generated check rides along, and lands at the repo root where
        # build.py's recursive check_*.py discovery will find it.
        check = payload.get("check")
        if check:
            stem = rel[:-3]
            items.append((f"check_{stem}.py", check))
        for name, text in items:
            path = ROOT / name
            if path.exists():
                STUDIO.backups.setdefault(name, path.read_text(encoding="utf-8"))
            else:
                # A file that did not exist has no previous contents to restore, so
                # reverting it means DELETING it. Recording None rather than
                # skipping the backup is what makes "revert" work for generated
                # art, which is the case where you most want a one-click undo: a
                # sprite whose own gate just failed should be removable, not
                # merely overwritten.
                STUDIO.backups.setdefault(name, None)
            path.write_text(text, encoding="utf-8")
            written.append(name)
        return self._json({"wrote": written, "bytes": len(source),
                           "revertable": all(w in STUDIO.backups for w in written)})

    def _revert(self, payload: dict):
        rel = (payload.get("path") or "").strip()
        if "/" in rel or "\\" in rel:
            return self._error("revert by bare filename, as written")
        # Restore the module and, if it was generated, the check written with it.
        # Reverting only one of the two leaves a check policing art that is no
        # longer there, which fails for the wrong reason.
        names = [rel, f"check_{rel[:-3]}.py"] if rel.endswith(".py") else [rel]
        restored, deleted = [], []
        for name in names:
            if name not in STUDIO.backups:
                continue
            previous = STUDIO.backups.pop(name)
            path = ROOT / name
            if previous is None:
                if path.exists():
                    path.unlink()
                deleted.append(name)
            else:
                path.write_text(previous, encoding="utf-8")
                restored.append(name)
        if not restored and not deleted:
            return self._error(f"no backup for {rel!r}; nothing to revert")
        return self._json({"reverted": restored, "deleted": deleted})

    # -- SSE ---------------------------------------------------------------
    def _stream(self, job_id: int):
        job = None
        for candidate in (STUDIO.current, STUDIO.last):
            if candidate and candidate.id == job_id:
                job = candidate
                break
        if job is None:
            return self._error(f"no job {job_id}", 404)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        cursor = 0
        try:
            while True:
                # Replay first, so a client that connects late still sees the
                # whole run; then block on the live queue.
                for seq, name, data in job.snapshot():
                    if seq <= cursor:
                        continue
                    cursor = seq
                    self._sse(name, data)
                if job.done.is_set() and cursor >= job.snapshot()[-1][0]:
                    break
                try:
                    seq, name, data = job.queue.get(timeout=0.25)
                    if seq > cursor:
                        cursor = seq
                        self._sse(name, data)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return                  # the page navigated away; not an error
        self._sse("close", {"job": job.id})

    def _sse(self, name: str, data) -> None:
        body = json.dumps(data, ensure_ascii=False)
        self.wfile.write(f"event: {name}\ndata: {body}\n\n".encode("utf-8"))
        self.wfile.flush()


# --------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="pixellint studio")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default=HOST,
                    help="defaults to loopback; this server runs processes")
    args = ap.parse_args(argv)

    if not UI_PATH.exists():
        print(f"missing {UI_PATH}", file=sys.stderr)
        return 1

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.daemon_threads = True
    url = f"http://{args.host}:{args.port}/"
    state = llm.describe()
    print(f"pixellint studio  {url}")
    print(f"repo              {ROOT}")
    print(f"model             {state['active']} / {state['active_model']}"
          f"{'' if state['ready'] else '  (no key yet -- set it on the page)'}")
    print("ctrl-c to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
