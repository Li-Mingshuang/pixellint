# The studio

A local page that runs the pipeline, streams what it is doing, and lets you stop it
or change something and rerun.

```bash
python studio/server.py            # http://127.0.0.1:8777
python studio/server.py --port 9000
```

Stdlib only -- no new dependency, no build step, no CDN, so it works offline.

## Why it exists

Every other tool in this repo answers *is it acceptable*. `evaluate.py` answers *how
much did it cost*. All of it is built on one admission: the authoring model cannot
see its own output, so claims about the art are assertions and numbers, never
judgements.

That leaves a gap that is not about correctness. A human looking at the result has
no cheap way to **watch** a generation, **stop** one that is going wrong, or make a
change and see its effect without waiting for a full build. The studio closes that
gap.

It adds no new checking. It runs the same steps, the same checks and the same
locked palettes, and shows you what they say as they say it.

## What it shows

| panel | where the content comes from |
|---|---|
| **Render steps / Checks** | `build.py`'s own registry, imported rather than restated, with its real `is_fresh()` per step -- so `cached` means the build would genuinely skip it |
| **Live output** | the step's stdout, line by line, as it is produced |
| **Problems** | every `FAIL` / `WARN` line, with *rerun* and *open the module this check polices* one click away |
| **Artifacts** | files the step itself announced, parsed out of its own `wrote :` lines |

A detail worth stating: **artifacts are announced by the step, not predicted by the
studio.** The studio reads what the step printed. A step that starts writing a new
file gets it into the gallery with nothing registered anywhere -- the same
"discover by shape, never from a maintained list" rule the rest of the repo follows.

## Halting

Halt kills the **process tree**, not the process. `render_game_gif.py` spawns node,
and node is not killed by terminating its parent. A stop that reports success while
a child keeps burning a core is worse than no stop, because it is a stop that lies.
`studio/check_studio.py` proves this with a parent that spawns a grandchild, then
requires both to be gone.

## Editing

Any module can be opened, edited and rerun. A generated module and its gate are
written together and can be reverted together; a module that did not exist before is
*deleted* on revert rather than left behind, because the case where you most want
one-click undo is a sprite whose own gate just failed.

## Generating with a model

The studio can ask a model for a sprite and stream it in. The division of labour is
the design:

> **The model authors the grid. The studio authors the module.**

Asking a model for a complete Python file gives it three jobs -- get the art right,
get the palette right, get the Python right -- and any one of them going wrong
produces a syntactically broken module whose traceback says nothing about the art.
So the contract is narrow: quoted rows, one per line, plus an optional
`PALETTE = "SCENE"`. `studio/llm.py` parses that tolerantly, resolves the palette
from this repo's own tables, wraps the rows in the module scaffold, and writes a
`check_*.py` for it at the same time.

Consequences worth having:

* a hallucinating model produces an ugly sprite, never an unparseable module
* it cannot substitute a palette, because it never writes the palette line
* it cannot skip the gate, because the gate is generated with the art
* model output is never executed anywhere in the request path: the live preview
  looks each character up in the palette table, and an unknown key draws **magenta**
  so it is impossible to miss

### Streaming, and the two channels

The sprite preview draws **as the rows arrive** -- sequential rows, not an
animation. Two protocol details make that honest rather than decorative:

* DeepSeek's reasoner puts its chain of thought in `delta.reasoning_content` and its
  answer in `delta.content`, and only one of the two is non-null per chunk. The
  studio keeps them on **separate channels**: reasoning is displayed dimmed, and only
  the content channel is parsed for grid rows. Feed both into the parser and the
  model's deliberations render as pixels.
* the `grid` event is throttled to the moments the picture can actually change (a new
  row, or a row whose width changed). Emitting the whole grid per token would put
  thousands of identical copies into the replay buffer for a preview that redraws
  identically.

### Configuring the model

Two ways. The key is a secret you should not have to hand to anyone, including to an
agent writing this code, so both paths keep it away from the browser.

**Environment variables:**

| variable | meaning |
|---|---|
| `PIXELLINT_LLM_PROVIDER` | `deepseek` \| `openai` \| `anthropic` \| `ollama` \| `offline` |
| `PIXELLINT_LLM_API_KEY` | the key |
| `PIXELLINT_LLM_MODEL` | override the model |
| `PIXELLINT_LLM_BASE_URL` | override the endpoint |

Falling back to `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`.

**Or paste it into the page.** It is held in the server process's memory for that
session: never written to disk, never committed, never returned over HTTP, never
logged, and cleared from the DOM after it is accepted. `check_studio.py` asserts the
non-leakage by installing a marker key and searching every response for it.

Wire formats: OpenAI-compatible (`/chat/completions` with `stream: true`) covers
DeepSeek, OpenAI, Ollama and any self-hosted gateway that speaks it; Anthropic uses
`/v1/messages`. DeepSeek defaults are `https://api.deepseek.com/v1` with
`deepseek-chat` or `deepseek-reasoner`.

**`offline`** needs no key and no network. It emits a fixed grid through the *real*
streaming path, so the whole loop can be exercised without spending anything. It is
the default when nothing is configured, and the page says so.

**What has not been verified.** The live API path has never been executed: there is
no key in this environment, and no call was made. The offline stub exercises the
same parsing, rendering, module-writing and gating code, and the transport is
written to the published wire format -- but "the transport has run against
api.deepseek.com" is not a claim this repo can make. Treat the first real call as
the test.

## What it deliberately does not do

* **No new assertions.** The studio shows the pipeline's verdicts; it does not add
  or soften any.
* **No beauty score.** Same reason as everywhere else here.
* **Not reachable off the machine.** It binds loopback only, because it spawns
  processes and can write files. It has no authentication because it is not exposed.
* **One job at a time.** Two builds write the same files; a second request while one
  is running is refused with 409 rather than interleaved.

## Cost

`studio/check_studio.py` drives a real HTTP server in-process and proves the
process-tree kill with real processes. That makes it the slowest check in the repo,
and it sits on the critical path of the verify wave.

Measured as a paired A/B on this 8-core machine -- same tree, only that one file
present or absent, three runs each:

| | without | with | marginal |
|---|---|---|---|
| incremental, nothing changed | 4.01 / 4.46 / 4.40 s | 5.98 / 6.06 / 5.86 s | **+1.6 s** |
| forced rebuild | 7.08 / 7.55 s | 11.88 / 10.09 s | +2 to +3 s, noisy |

The check is 2.5 s standalone; under the verify wave's contention it costs a little
more. Absolute numbers on this machine drift by ~0.5 s run to run and by more across
sessions, so the marginal column is the one to trust.

Two cheap reductions were taken and are worth recording, because both were found by
measuring rather than reasoning:

* `build.py` now caches each module's AST imports against its mtime. The freshness
  test re-parsed `pixelkit.py` once per step; the `/api/plan` endpoint made that
  visible, and the fix speeds up the build too.
* the liveness probe shells out to `tasklist` on Windows (~200 ms a call), so it is
  consulted a bounded number of times instead of polled in a loop. This alone took
  the check from 3.8 s to 2.5 s.

Making checks cacheable was considered and **not** done: it is a new correctness
bargain ("this check did not run"), and it should be taken deliberately on its own
measurement rather than as a side effect of adding a tool. It is recorded in
[decisions.md](decisions.md) so it can be revisited on its merits.
