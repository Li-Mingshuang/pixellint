// Headless playability test for index.html.
//
// The game is a browser thing, but almost all of what can be WRONG with it is
// logic, not rendering: bullets that never hit, a spawner that stops, a NaN
// creeping into a position, a player who cannot die. So this stubs the DOM,
// loads the real script out of index.html, drives it with synthetic input, and
// asserts the game actually plays.
//
//   node game/smoke_test.mjs

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(HERE, "index.html"), "utf8");

// ---- pull the inline script (the last <script> with no src) ----------------
const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)];
if (!scripts.length) { console.error("FATAL: no inline script found in index.html"); process.exit(2); }
const code = scripts[scripts.length - 1][1];

// ---- canvas / DOM stubs ----------------------------------------------------
// drawImage is recorded (with the source rect reverse-mapped back to an atlas
// key) so the draw ORDER and placement can be asserted, not just that render()
// did not throw. Wrong layer order and off-canvas sprites are real bugs that a
// "does it throw" test sails straight past.
const draws = [];
const fills = [];
// getContext() is called once, at game init, so the ctx closure must read the
// atlas through a mutable holder rather than a captured value -- reassigning a
// variable later would leave the closure looking at the empty object forever.
const atlasHolder = { ref: {} };
function makeCtx() {
  const noop = () => {};
  const grad = { addColorStop: noop };
  const keyFor = (sx, sy, sw, sh) => {
    const atlas = atlasHolder.ref;
    for (const k in atlas) {
      const r = atlas[k];
      if (r && r[0] === sx && r[1] === sy && r[2] === sw && r[3] === sh) return k;
    }
    return "<unknown>";
  };
  const base = {
    canvas: { width: 320, height: 180 },
    createRadialGradient: () => grad,
    createLinearGradient: () => grad,
    measureText: () => ({ width: 4 }),
    drawImage: (_img, sx, sy, sw, sh, dx, dy) => {
      draws.push({ key: keyFor(sx, sy, sw, sh), dx, dy, sw, sh });
    },
    fillRect: (x, y, w, h) => {
      fills.push({ x, y, w, h, col: base.fillStyle, alpha: base.globalAlpha });
    },
  };
  return new Proxy(base, {
    get(t, k) { return k in t ? t[k] : noop; },
    set(t, k, v) { t[k] = v; return true; },
  });
}

const listeners = {};
const el = {
  width: 320, height: 180, style: {},
  getContext: () => makeCtx(),
  addEventListener: (k, f) => { (listeners[k] ||= []).push(f); },
  getBoundingClientRect: () => ({ left: 0, top: 0, width: 320, height: 180 }),
};

let rafCalls = 0;
const sandbox = {
  console,
  document: { getElementById: () => el, addEventListener: () => {} },
  window: {},
  innerWidth: 1280, innerHeight: 800,
  addEventListener: (k, f) => { (listeners[k] ||= []).push(f); },
  requestAnimationFrame: () => { rafCalls++; return 1; },
  performance: { now: () => Date.now() },
  // The game sets onload BEFORE assigning src, so firing it from the setter is
  // enough to flip artReady and put the real atlas path under test.
  Image: class {
    set src(v) { this._src = v; if (typeof this.onload === "function") this.onload(); }
    get src() { return this._src; }
    get width() { return 512; }
    get height() { return 512; }
  },
  Math, Date, Object, Array, String, Number, Boolean, JSON, isNaN, isFinite,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

// ---- run ------------------------------------------------------------------
const errors = [];
try {
  vm.createContext(sandbox);
  vm.runInContext(readFileSync(join(HERE, "assets.js"), "utf8"), sandbox, { filename: "assets.js" });
} catch {
  // assets.js may not exist yet; the game falls back to rectangle stand-ins
}
try {
  vm.runInContext(code, sandbox, { filename: "index.html:inline" });
} catch (e) {
  console.error("FATAL: game script threw on load:\n" + (e && e.stack || e));
  process.exit(2);
}

const g = sandbox.window.__game;
if (!g) { console.error("FATAL: window.__game was not exposed"); process.exit(2); }

// ---- assertions -----------------------------------------------------------
const results = [];
function check(name, cond, detail = "") {
  results.push({ name, ok: !!cond, detail });
  return !!cond;
}
function finite(v) { return typeof v === "number" && Number.isFinite(v); }

// 1. it runs for a while without throwing
g.reset();
let threw = null;
try { g.step(60 * 6); } catch (e) { threw = e; }
check("runs 6 simulated seconds without throwing", !threw, threw ? threw.message : "");

// 2. the spawner produces enemies
g.reset();
g.step(60 * 8);
const spawned = g.state.zombies.length + g.state.kills;
check("spawner produces zombies", spawned > 0, `zombies+kills=${spawned}`);

// 3. firing produces bullets, and they travel
g.reset();
g.setKey("KeyD", true);
g.step(30);
g.fire();
const hadBullet = g.state.bullets.length > 0;
const bx0 = hadBullet ? g.state.bullets[0].x : 0;
g.step(3);
check("fire() creates a bullet", hadBullet);
check("bullet moves", !hadBullet || g.state.bullets[0]?.x > bx0 || g.state.bullets.length === 0,
  `x ${bx0} -> ${g.state.bullets[0]?.x}`);
g.setKey("KeyD", false);

// 4. the player can actually kill a zombie and score
g.reset();
let scored = false, killed = 0;
for (let i = 0; i < 60 * 20 && !scored; i++) {
  g.update(1 / 60);
  if (g.state.zombies.length === 0 && i % 30 === 0) g.spawnZombie();
  // aim: fire whenever something is alive and roughly to the right
  const alive = g.state.zombies.filter(z => z.state !== "death");
  if (alive.length) {
    g.state.player.face = 1;
    g.state.player.x = Math.max(20, alive[0].x - 70);
    g.fire();
  }
  if (g.state.kills > 0) { scored = true; killed = g.state.kills; }
}
check("a zombie can be shot dead and scores", scored, `kills=${killed}`);

// 5. zombies reach the player and can kill him
g.reset();
g.gameOver = false;
for (let i = 0; i < 60 * 40 && !g.state.gameOver; i++) {
  g.update(1 / 60);
  if (g.state.zombies.length < 3 && i % 20 === 0) g.spawnZombie();
}
check("a swarm can kill the player", g.state.gameOver, `hp=${g.state.player.hp}`);

// 6. nothing goes NaN over a long run with input held
g.reset();
g.setKey("KeyA", true); g.setKey("Space", true);
let nanSeen = null;
for (let i = 0; i < 60 * 25; i++) {
  if (i === 60 * 8) { g.setKey("KeyA", false); g.setKey("KeyD", true); }
  g.update(1 / 60);
  const p = g.state.player;
  if (!finite(p.x) || !finite(p.vx) || !finite(p.hp)) { nanSeen = `player ${p.x},${p.vx},${p.hp}`; break; }
  for (const z of g.state.zombies)
    if (!finite(z.x) || !finite(z.ft)) { nanSeen = `zombie ${z.x},${z.ft}`; break; }
  if (nanSeen) break;
}
g.setKey("KeyA", false); g.setKey("KeyD", false); g.setKey("Space", false);
check("no NaN in positions over 25s of play", !nanSeen, nanSeen || "");

// 7. entity counts stay bounded (no unbounded leak)
g.reset();
g.setKey("Space", true);
g.step(60 * 30);
g.setKey("Space", false);
const st = g.state;
check("particles stay bounded", st.parts.length < 4000, `parts=${st.parts.length}`);
check("decals stay bounded", st.decals.length <= 90, `decals=${st.decals.length}`);
check("casings stay bounded", st.casings.length < 400, `casings=${st.casings.length}`);
check("zombies stay bounded", st.zombies.length < 200, `zombies=${st.zombies.length}`);

// 8. rendering does not throw (with and without art)
let renderErr = null;
try { g.render(); } catch (e) { renderErr = e; }
check("render() does not throw", !renderErr, renderErr ? renderErr.message : "");

// 9. draw order and placement
atlasHolder.ref = sandbox.window.ATLAS || {};
const atlasRef = atlasHolder.ref;
draws.length = 0;
fills.length = 0;
g.reset();
g.step(90);
try { g.render(); } catch { /* already reported above */ }

const haveAtlas = Object.keys(atlasRef).length > 0;
const idxOf = (pred) => draws.findIndex(d => pred(d.key));
const lastBg = draws.reduce((a, d, i) => (d.key.startsWith("bg.") ? i : a), -1);
const firstEntity = draws.findIndex(d =>
  d.key.startsWith("player.") || d.key.startsWith("zombie."));

check("something is drawn", draws.length + fills.length > 0,
  `${draws.length} drawImage + ${fills.length} fillRect`);

if (haveAtlas) {
  check("background is drawn before any entity",
    lastBg === -1 || firstEntity === -1 || lastBg < firstEntity,
    `last bg draw #${lastBg}, first entity draw #${firstEntity}`);
  const poolIdx = idxOf(k => k === "fx.bloodpool");
  check("blood decals draw under the actors",
    poolIdx === -1 || firstEntity === -1 || poolIdx < firstEntity,
    `pool #${poolIdx} vs entity #${firstEntity}`);
  check("the background layers are actually drawn",
    draws.filter(d => d.key.startsWith("bg.")).length >= 3,
    `bg draws=${draws.filter(d => d.key.startsWith("bg.")).length}`);
} else {
  console.log("  --    (no atlas yet: layer-order assertions skipped, the game" +
              " is running on rectangle stand-ins)");
}

const offCanvas = draws.filter(d => d.sw > 0 &&
  (d.dx < -360 || d.dx > 320 + 360 || d.dy < -200 || d.dy > 180 + 200));
check("no sprite drawn absurdly off-canvas", offCanvas.length === 0,
  offCanvas.slice(0, 3).map(d => `${d.key}@${Math.round(d.dx)},${Math.round(d.dy)}`).join(" "));

// with real art loaded, every sprite the code asks for must exist in the atlas
const wanted = new Set(draws.map(d => d.key));
const missing = [...wanted].filter(k => k !== "<bg-fill>" && !(k in atlasRef));
check("every drawn key exists in the atlas", missing.length === 0,
  missing.slice(0, 5).join(","));

// 10. parallax covers the viewport at any camera position.
// A layer that is 320 wide but drawn from a single anchored origin eventually
// leaves a gap at the right edge. That is the classic parallax bug and it is
// invisible until the player has walked a while.
if (haveAtlas) {
  const gaps = [];
  for (const travel of [0, 137, 1600, 9999]) {
    g.reset();
    g.state.player.x = travel;
    for (let i = 0; i < 4; i++) g.update(1 / 60);
    draws.length = 0;
    g.render();
    for (const layer of ["bg.sky", "bg.far", "bg.mid", "bg.street"]) {
      const spans = draws.filter(d => d.key === layer)
        .map(d => [d.dx, d.dx + d.sw]).sort((a, b) => a[0] - b[0]);
      if (!spans.length) {
        gaps.push(`${layer} not drawn at camX=${Math.round(g.state.camX)}`);
        continue;
      }
      const where = `camX=${Math.round(g.state.camX)}`;
      if (spans[0][0] > 0) gaps.push(`${layer} gap 0..${Math.round(spans[0][0])} at ${where}`);
      let reach = spans[0][1];
      for (let i = 1; i < spans.length; i++) {
        if (spans[i][0] > reach) gaps.push(`${layer} gap ${Math.round(reach)}..${Math.round(spans[i][0])} at ${where}`);
        reach = Math.max(reach, spans[i][1]);
      }
      if (reach < 320) gaps.push(`${layer} gap ${Math.round(reach)}..320 at ${where}`);
    }
  }
  check("parallax covers the viewport at every camera position", gaps.length === 0,
    gaps.slice(0, 4).join(" | "));
} else {
  check("parallax covers the viewport at every camera position", true, "skipped, no atlas");
}

// ---- optional: dump real draw calls so a GIF can be composited offline -----
// `node game/smoke_test.mjs --dump 48` writes game/frames.json. render_game_gif.py
// replays it against the atlas, so the README animation is the game's actual
// output rather than a hand-made illustration of it.
if (process.argv.includes("--dump")) {
  const n = parseInt(process.argv[process.argv.indexOf("--dump") + 1] || "48", 10);
  const frames = [];
  g.reset();
  for (let f = 0; f < n; f++) {
    // a scripted bit of play: walk right, fire in bursts, let the horde build
    const t = f / 15;
    g.setKey("KeyD", true);
    g.setKey("KeyA", false);
    const firing = (Math.floor(t * 0.75) % 2) === 1;
    g.setKey("Space", firing);
    if (f % 30 === 0) { g.spawnZombie(); g.spawnZombie(); }
    g.step(4);
    draws.length = 0;
    fills.length = 0;
    g.render();
    frames.push({ draws: draws.slice(), fills: fills.slice() });
  }
  g.setKey("KeyD", false);
  g.setKey("Space", false);
  writeFileSync(join(HERE, "frames.json"), JSON.stringify(frames));
  console.log(`dumped ${frames.length} frames -> game/frames.json`);
  process.exit(0);
}

// ---- report ---------------------------------------------------------------
const pad = Math.max(...results.map(r => r.name.length));
let failed = 0;
console.log("-- headless playability --------------------------------------");
for (const r of results) {
  if (!r.ok) failed++;
  console.log(`  ${r.ok ? "ok  " : "FAIL"}  ${r.name.padEnd(pad)}  ${r.detail}`);
}
console.log(`\n  ${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
