"""Model adapters for the studio's generate-and-check loop.

Standard library only, because the rest of this repo has one dependency and this
is not a good reason to add a second.

THE DIVISION OF LABOUR IS THE DESIGN
------------------------------------
The model authors the GRID. This module authors the MODULE.

Asking a model to emit a complete Python file gives it three jobs -- get the art
right, get the palette right, get the Python right -- and any of the three going
wrong produces a syntactically broken module whose traceback says nothing about
the art. So the contract is narrower: the model emits quoted rows, one per line,
plus an optional `PALETTE = "SCENE"` line. `extract_grid()` parses that
tolerantly (it has to run on PARTIAL text, because the studio renders the sprite
while it is still streaming), `module_source()` wraps it in the scaffold this
repo already uses -- docstring, `SHIPPED`, `PALETTE`, `main()` -- and the palette
is resolved from this repo's own locked palettes, never from model output. A
hallucinating model can therefore produce an ugly sprite. It cannot produce a
module that bypasses the palette, and it cannot produce one that does not parse.

Nothing in this file executes model output. `extract_grid()` reads strings.

CONFIGURATION
-------------
Two ways, and the second exists because a key is a secret the user should not have
to hand to anyone -- including to an agent writing this code.

1. Environment variables. No config file, because a config file is where keys end
   up committed.

       PIXELLINT_LLM_PROVIDER   openai | deepseek | anthropic | ollama | offline
       PIXELLINT_LLM_API_KEY    the key (or leave it to the provider's own var below)
       PIXELLINT_LLM_MODEL      override the default model
       PIXELLINT_LLM_BASE_URL   override the endpoint

   Falling back to the usual per-provider variables:

       openai    OPENAI_API_KEY
       deepseek  DEEPSEEK_API_KEY
       anthropic ANTHROPIC_API_KEY
       ollama    (none needed -- local)

2. `set_session()`, called by the studio server when the key is typed into the
   page. It lives in this process's memory for that session only: never written to
   disk, never returned to the browser, never logged. `describe()` reports only
   WHETHER a session key is set, never the value.

`offline` needs no key and no network. It emits a real grid through the real
streaming path, so the studio can be exercised end to end without spending
anything or being online.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Iterator

# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Provider:
    name: str
    kind: str                 # "openai" | "anthropic" | "offline"
    base_url: str
    key_env: str | None
    default_model: str
    note: str = ""
    extra_env: tuple = field(default=())


PROVIDERS: dict = {
    "openai": Provider(
        name="openai", kind="openai",
        base_url="https://api.openai.com/v1",
        key_env="OPENAI_API_KEY", default_model="gpt-4o-mini",
    ),
    "deepseek": Provider(
        name="deepseek", kind="openai",
        base_url="https://api.deepseek.com/v1",
        key_env="DEEPSEEK_API_KEY", default_model="deepseek-chat",
        note="reasoner puts its chain of thought in reasoning_content",
    ),
    "anthropic": Provider(
        name="anthropic", kind="anthropic",
        base_url="https://api.anthropic.com",
        key_env="ANTHROPIC_API_KEY", default_model="claude-sonnet-4-5",
    ),
    "ollama": Provider(
        name="ollama", kind="openai",
        base_url="http://127.0.0.1:11434/v1",
        key_env=None, default_model="qwen2.5-coder:7b",
        note="local; needs no key",
    ),
    "offline": Provider(
        name="offline", kind="offline",
        base_url="", key_env=None, default_model="offline-stub",
        note="no network, no key: emits a fixed grid through the real stream path",
    ),
}

# For the UI's model picker. Not a whitelist -- any model string is accepted, and
# self-hosted gateways carry model names no list here could know.
KNOWN_MODELS: dict = {
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
    "anthropic": ["claude-sonnet-4-5", "claude-haiku-4-5"],
    "ollama": ["qwen2.5-coder:7b", "llama3.1:8b"],
    "offline": ["offline-stub"],
}


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


# Session overrides, set from the studio page. Memory only, by design.
_session: dict = {"provider": None, "model": None, "key": None, "base_url": None}


def set_session(provider: str | None = None, model: str | None = None,
                key: str | None = None, base_url: str | None = None) -> None:
    """Install a session-only provider/key. Anything falsy leaves the slot alone.

    There is deliberately no getter for `key`. The only code that may read it is
    `resolve()`, which hands it straight to the transport.
    """
    for slot, value in (("provider", provider), ("model", model),
                        ("key", key), ("base_url", base_url)):
        if value:
            _session[slot] = value.strip() if isinstance(value, str) else value


def clear_session() -> None:
    for slot in _session:
        _session[slot] = None


def session_state() -> dict:
    """What the UI may know about the session key: that it exists, not what it is."""
    return {
        "provider": _session["provider"],
        "model": _session["model"],
        "base_url": _session["base_url"],
        "key_set": bool(_session["key"]),
        "key_source": "page" if _session["key"] else None,
    }


def resolve(provider_name: str | None = None, model: str | None = None):
    """Pick a provider and report how it was configured.

    Returns (Provider, model, key). Session values beat the environment; the
    environment beats the default.
    """
    name = (provider_name or _session["provider"]
            or _env("PIXELLINT_LLM_PROVIDER") or "").lower() or None
    if name is None:
        # Auto-detect: an explicit key in the environment is a clear enough
        # signal of intent. Order matters -- first match wins.
        for candidate in ("deepseek", "anthropic", "openai"):
            if _env(PROVIDERS[candidate].key_env or ""):
                name = candidate
                break
    if name not in PROVIDERS:
        name = "offline"

    provider = PROVIDERS[name]
    base = _session["base_url"] or _env("PIXELLINT_LLM_BASE_URL") or provider.base_url
    key = _session["key"]
    if key is None:
        key = _env("PIXELLINT_LLM_API_KEY")
    if key is None and provider.key_env:
        key = _env(provider.key_env)
    provider = Provider(**{**provider.__dict__, "base_url": base})
    chosen = (model or _session["model"] or _env("PIXELLINT_LLM_MODEL")
              or provider.default_model)
    return provider, chosen, key


def describe() -> dict:
    """Everything the UI may know. Deliberately not the key itself."""
    out = []
    for name, p in PROVIDERS.items():
        key = _env("PIXELLINT_LLM_API_KEY") or (_env(p.key_env) if p.key_env else None)
        in_session = _session["provider"] == name and bool(_session["key"])
        out.append({
            "name": name,
            "kind": p.kind,
            "model": _session["model"] or _env("PIXELLINT_LLM_MODEL") or p.default_model,
            "models": KNOWN_MODELS.get(name, []),
            "base_url": _session["base_url"] or _env("PIXELLINT_LLM_BASE_URL") or p.base_url,
            "key_env": p.key_env,
            "configured": bool(key) or in_session or p.key_env is None,
            "note": p.note,
        })
    active, model, key = resolve()
    return {
        "providers": out,
        "active": active.name,
        "active_model": model,
        "active_base_url": active.base_url,
        "ready": active.kind == "offline" or bool(key),
        "session": session_state(),
    }


# --------------------------------------------------------------------------
# The prompt. Narrow on purpose: grid rows in, grid rows out.
# --------------------------------------------------------------------------

SYSTEM = """You are a pixel-art sprite author. You emit GRIDS, not code.

Output format -- exactly this, nothing else:
- One double-quoted string per row of the grid, one row per line.
- One character per pixel.
- The special character "." means transparent.
- Every other character must be a palette key listed below.
- All rows MUST be the same length.
- Optionally, a single final line: PALETTE = "SCENE"  (or "GAME")

NO commas. NO brackets. NO code fences. NO blank lines between rows. NO prose,
headings, or explanations. Only the quoted rows, like this:

"KKKKKKKK"
"KwwwwwwK"
"KwEEwwEK"
"KKKKKKKK"

Why the constraints exist: the grid IS the artwork. It is diffable, readable, and
every adjacent pair of colours is machine-checked for whether a human can tell
them apart. A character that is not a palette key is not a colour -- it is a row
that cannot be drawn, and it will be REJECTED rather than guessed at, leaving a
hole in the sprite. Art that reads well at this size uses a dark outline around the
whole silhouette, at most three or four tones for shading, and light coming from
one consistent direction.
"""


def build_prompt(rows_hint: int, cols_hint: int, palette_name: str,
                 palette: dict, palette_help: str) -> str:
    keys = " ".join(sorted(k for k in palette if k != "."))
    return (
        f"Author a sprite on a {cols_hint} wide by {rows_hint} tall grid.\n\n"
        f"Palette ({palette_name}): {keys}\n\n"
        f"{palette_help}\n"
    )


# --------------------------------------------------------------------------
# Tolerant parsing -- must work on PARTIAL text, because the studio renders the
# sprite while it is still arriving.
# --------------------------------------------------------------------------

_ROW = re.compile(r'"((?:[^"\\]|\\.)*)"')
_PAL = re.compile(r'PALETTE\s*=\s*"([A-Za-z_]+)"')


def extract_grid(text: str, allowed: set | None = None, max_rows: int = 200) -> dict:
    """Pull quoted rows out of streamed text. Never executes anything.

    Models ignore instructions. Ask for quoted rows and nothing else and you will
    still get a docstring, a fenced code block, a Python list literal, or a
    sentence explaining the sprite. So this parser is tolerant about FORM and
    strict about CONTENT, and it REPORTS what it rejected instead of dropping it
    quietly.

    That last part is the important one. The first version of this silently
    discarded any row it did not like, and the failure it produced was a blank
    sprite with no explanation: a real DeepSeek call came back as a 16x1 grid of
    transparent pixels, because

        "KKKKKKKK",

    -- a row with a trailing comma, the most natural thing for a model that has
    seen a million Python list literals -- ended with a comma rather than a quote,
    so EVERY row was dropped. The comma carries no information about the art, and
    rejecting it was pedantry with a silent, expensive consequence.

    Tolerated form: trailing commas, list brackets, code fences, blank lines,
    indentation, surrounding prose. Rejected content, and reported: a row using a
    character that is not a palette key (drawn nowhere rather than guessed at), a
    row whose closing quote has not arrived yet, or a row of whitespace.
    """
    rows: list = []
    rejected: list = []
    unknown: dict = {}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or '"""' in stripped:
            continue
        if stripped.upper().startswith("PALETTE"):
            continue
        # A trailing comma is punctuation from a list literal, not art. Strip it
        # before deciding whether the row is complete.
        probe = stripped.rstrip(",").rstrip()
        if not probe.endswith('"'):
            # A line that looks like the start of a row but has no closing quote is
            # still arriving -- not an error, just not usable yet.
            if probe.startswith('"'):
                rejected.append(("still arriving", stripped[:48]))
            continue
        found = _ROW.findall(probe)
        if len(found) != 1:
            rejected.append((f"{len(found)} quoted strings on one line", stripped[:48]))
            continue
        row = found[0]
        if not row:
            rejected.append(("empty row", stripped[:48]))
            continue
        if any(ch.isspace() for ch in row):
            rejected.append(("whitespace inside a row", stripped[:48]))
            continue
        if allowed is not None:
            stray = set(row) - allowed
            if stray:
                for ch in stray:
                    unknown[ch] = unknown.get(ch, 0) + row.count(ch)
                rejected.append((f"not palette keys: {''.join(sorted(stray))}",
                                 stripped[:48]))
                continue
        rows.append(row)
        if len(rows) >= max_rows:
            break

    # search(), not match(): the PALETTE line arrives at the END of the stream, so
    # anchoring at position 0 could never find it and every grid silently stayed
    # on the default palette.
    pal = _PAL.search(text)
    widths = sorted({len(r) for r in rows})
    return {
        "rows": rows,
        "palette": pal.group(1).upper() if pal else None,
        # `uniform` describes ONLY what has arrived. An earlier version called a
        # one-row grid "complete" -- widths has length 1, so the uniformity test
        # passed -- and the UI announced a finished sprite on the first line of a
        # stream. Whether the grid is writable is decided by module_source(),
        # which validates for real; this function reports and does not judge.
        "uniform": len(widths) == 1,
        "widths": widths,
        "width": len(rows[0]) if rows else 0,
        "height": len(rows),
        # So the studio can say WHY a grid came out wrong instead of showing an
        # empty canvas and letting the user guess.
        "rejected": rejected[-40:],
        "rejected_count": len(rejected),
        "unknown_keys": dict(sorted(unknown.items(), key=lambda kv: -kv[1])),
        "opaque": sum(1 for r in rows for ch in r if ch != "."),
    }


def module_source(name: str, rows: list, palette_name: str, meta: dict) -> str:
    """Wrap model-authored rows in this repo's module scaffold.

    The scaffold is generated here rather than by the model, so an unparseable
    response is impossible by construction and the palette cannot be talked
    around. `palette_name` is validated against this repo's real palettes; an
    unknown name is a hard error rather than a silent fallback, because a silent
    fallback is how a GAME-palette sprite ends up rendered in SCENE colours and
    every check then reports on the wrong image.
    """
    if palette_name not in ("SCENE", "GAME"):
        raise ValueError(f"unknown palette {palette_name!r}; expected SCENE or GAME")
    if not rows:
        raise ValueError("no grid rows to write")
    widths = sorted({len(r) for r in rows})
    if len(widths) != 1:
        raise ValueError(f"ragged grid: row widths {widths}")
    # Art with no pixels is not art, and writing it produces a module that is
    # guaranteed to fail its own gate -- a wasted round trip and a confusing
    # "fully transparent" message that says nothing about the real cause. Refusing
    # here turns it into one clear error at the moment it happens.
    opaque = sum(1 for r in rows for ch in r if ch != ".")
    if not opaque:
        raise ValueError(
            f"the grid is entirely transparent ({len(rows)}x{len(rows[0])} of '.'); "
            f"nothing would be drawn")

    # FRAMES is a list of FRAMES, i.e. a list of grids -- the shape mech.FRAMES,
    # dog.DOG_FRAMES and walk_cycle.FRAMES all use, and the shape evaluate.py and
    # every check_*.py iterate. A first version emitted the rows directly as
    # FRAMES, so each ROW was treated as a frame: the generated gate then reported
    # "floating pixels" at column 0 of rows 11, 12 and 13, which is what checking a
    # single row of a sprite looks like. The art was fine; the shape was wrong, and
    # only running the generated gate revealed it.
    body = "\n".join(f'        "{row}",' for row in rows)
    provider = meta.get("provider", "?")
    model = meta.get("model", "?")
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    stem = name[:-3] if name.endswith(".py") else name
    return f'''"""{len(rows[0])}x{len(rows)} sprite authored through the studio.

Generated by {provider} / {model} on {stamp}.

The grid is the artwork. This scaffold is written by studio/llm.py, NOT by the
model: the model emits quoted rows and nothing else, so it cannot substitute a
palette, cannot emit code that does not parse, and cannot bypass the checks. Run
`python {stem}.py` for a preview; `check_{stem}.py` (written alongside this file)
is the gate, and build.py discovers it automatically.

FRAMES is a list of frames, each frame a grid -- one frame here, matching the
shape the rest of this repo uses.
"""

from gamepalette import GAME_PALETTE
from pixelkit import SCENE_PALETTE

_PALETTES = {{"SCENE": SCENE_PALETTE, "GAME": GAME_PALETTE}}

PALETTE_NAME = "{palette_name}"
PALETTE = _PALETTES[PALETTE_NAME]

SHIPPED = ("FRAMES",)

FRAMES = [
    [
{body}
    ],
]


def main() -> int:
    from pixelkit import build, check_grid, preview

    problems = []
    for i, grid in enumerate(FRAMES):
        problems.extend(check_grid(grid, f"{stem}.FRAMES[{{i}}]", palette=PALETTE))
    for p in problems:
        print(f"  FAIL  {{p}}")
    print(f"frames    : {{len(FRAMES)}} at {{len(FRAMES[0][0])}}x{{len(FRAMES[0])}}  "
          f"palette {{PALETTE_NAME}}")
    out = build(FRAMES[0], palette=PALETTE)
    preview(out, 8).save("assets/{stem}_preview.png")
    print("wrote     : assets/{stem}_preview.png")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def check_source(stem: str, palette_name: str, meta: dict) -> str:
    """The gate for a generated module, written at the same time as the art.

    Generated art and its assertion are produced together on purpose. The whole
    premise of this repo is that a model cannot see what it made, so art that
    arrives without a gate arrives unverified -- and a gate added later, by
    someone in a hurry, is a gate that never gets added. `build.py` discovers
    `check_*.py` recursively, so this file starts gating the moment it is written,
    with nothing to register.

    It asserts what is assertable about a standalone sprite and nothing more: the
    repo's own structural rules, and the separation rule over every adjacent colour
    pair. It does not pretend to judge whether the sprite is any good.
    """
    provider = meta.get("provider", "?")
    model = meta.get("model", "?")
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return f'''"""Verification for {stem}.py, a sprite authored by a model.

Written by studio/llm.py on {stamp} for {provider} / {model}.

A sprite a model drew cannot be reviewed by the model that drew it, so the things
that are checkable are checked and the rest is left to a human:

  * structure   - rectangular, palette-only, one closed connected body per frame
  * readability - the separation rule (dE76 plus a lightness edge) over every
                  adjacent colour pair, against the role floors

    python check_{stem}.py

Exits non-zero if anything fails.
"""

from {stem} import FRAMES, PALETTE, PALETTE_NAME
from pixelkit import SPRITE_TIERS, check_grid, report_separation

LABEL = "{stem}"


def main() -> int:
    problems = []

    print(f"-- structure ({{LABEL}}, {{PALETTE_NAME}} palette) " + "-" * 12)
    if not FRAMES:
        problems.append(f"{{LABEL}} exports no frames")
        print("  FAIL  no frames to check")
    for i, grid in enumerate(FRAMES):
        found = check_grid(grid, f"{{LABEL}}.FRAMES[{{i}}]", palette=PALETTE)
        for problem in found:
            problems.append(problem)
        if not found:
            print(f"  ok    frame {{i}}: {{len(grid[0])}}x{{len(grid)}}, "
                  f"palette-only, one closed body")
        else:
            for problem in found:
                print(f"  FAIL  frame {{i}}: {{problem}}")

    print("\\n-- colour separation ----------------------------------------")
    total_fails = 0
    for i, grid in enumerate(FRAMES):
        failures, rows = report_separation(
            grid, f"{{LABEL}}[{{i}}]", palette=PALETTE, tiers=SPRITE_TIERS)
        total_fails += len(failures)
        for message in failures:
            problems.append(message)
        if not failures:
            print(f"  ok    frame {{i}}: all {{len(rows)}} adjacent pairs pass")
    if total_fails:
        print(f"  FAIL  {{total_fails}} pair(s) below threshold")

    print()
    for problem in problems:
        print(f"  FAIL  {{problem}}")
    print(f"failures: {{len(problems)}}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


# --------------------------------------------------------------------------
# Streaming transport
# --------------------------------------------------------------------------


def _post_stream(url: str, payload: dict, headers: dict, timeout: float = 120.0):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)


def _iter_openai(response) -> Iterator[tuple]:
    """Yield (channel, text) from an OpenAI-compatible SSE stream.

    The channel matters and is not cosmetic. DeepSeek's reasoner puts its chain
    of thought in `delta.reasoning_content` and its answer in `delta.content`,
    and the official streaming example shows only one of the two is non-null per
    chunk. Feed both into the grid parser and the sprite preview renders the
    model's deliberations as pixels -- quoted strings inside the reasoning become
    grid rows. So reasoning is a separate channel that the UI can display and the
    parser ignores.
    """
    for raw in response:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        body = line[5:].strip()
        if body == "[DONE]":
            return
        try:
            chunk = json.loads(body)
        except json.JSONDecodeError:
            continue
        for choice in chunk.get("choices", []):
            delta = choice.get("delta") or {}
            if delta.get("reasoning_content"):
                yield ("reasoning", delta["reasoning_content"])
            if delta.get("content"):
                yield ("content", delta["content"])


def _iter_anthropic(response) -> Iterator[tuple]:
    for raw in response:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        try:
            chunk = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        if chunk.get("type") != "content_block_delta":
            continue
        delta = chunk.get("delta") or {}
        if delta.get("type") == "thinking_delta" and delta.get("thinking"):
            yield ("reasoning", delta["thinking"])
        elif delta.get("text"):
            yield ("content", delta["text"])


# The offline stub. A real grid, emitted in small pieces through the same code
# path as a network stream, so the UI's incremental render is genuinely exercised
# when there is no key and no network.
_OFFLINE_ROWS = [
    "....KKKKKK....",
    "..KKwwwwwwKK..",
    ".KwwwwwwwwwwK.",
    ".KwwEEwwEEwwK.",
    ".KwwEEwwEEwwK.",
    ".KwwwwwwwwwwK.",
    ".KwwwKKKKwwwK.",
    ".KwwwwwwwwwwK.",
    "..KwwwwwwwwK..",
    "...KKwwwwKK...",
    "..KttKKKKttK..",
    "..Ktt....ttK..",
    "..KKK....KKK..",
    "...KK....KK...",
]


def _offline_stream(abort) -> Iterator[tuple]:
    """Yield the stub grid the way a model would: a few characters at a time."""
    time.sleep(0.25)
    yield ("content", '"""offline stub -- no model was called."""\n')
    for row in _OFFLINE_ROWS:
        if abort():
            return
        time.sleep(0.06)
        piece = f'"{row}"\n'
        for i in range(0, len(piece), 3):
            if abort():
                return
            time.sleep(0.012)
            yield ("content", piece[i:i + 3])
    yield ("content", 'PALETTE = "SCENE"\n')


def stream(prompt_messages, provider: Provider, model: str, key: str | None,
           abort) -> Iterator[tuple]:
    """Yield (channel, text) deltas.

    `abort()` is polled between chunks, so a halt lands mid-stream rather than
    after the model has finished and the money is spent.
    """
    if provider.kind == "offline":
        yield from _offline_stream(abort)
        return

    if provider.kind == "anthropic":
        url = provider.base_url.rstrip("/") + "/v1/messages"
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if key:
            headers["x-api-key"] = key
        system = "\n".join(m["content"] for m in prompt_messages if m["role"] == "system")
        user = "\n".join(m["content"] for m in prompt_messages if m["role"] != "system")
        payload = {
            "model": model,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "stream": True,
        }
        parse = _iter_anthropic
    else:
        url = provider.base_url.rstrip("/") + "/chat/completions"
        headers = {"content-type": "application/json"}
        if key:
            headers["authorization"] = f"Bearer {key}"
        payload = {"model": model, "messages": prompt_messages, "stream": True}
        parse = _iter_openai

    try:
        response = _post_stream(url, payload, headers)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"{provider.name} returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"could not reach {provider.name} at {url}: {exc.reason}") from exc

    with response:
        for piece in parse(response):
            if abort():
                return
            yield piece
