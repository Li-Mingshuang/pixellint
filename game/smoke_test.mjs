// Headless playability test for index.html.
//
// The game is a browser thing, but almost all of what can be WRONG with it is
// logic, not rendering: bullets that never hit, a spawner that stops, a NaN
// creeping into a position, a player who cannot die. So this stubs the DOM,
// loads the real script out of index.html, drives it with synthetic input, and
// asserts the game actually plays.
//
//   node game/smoke_test.mjs

import { readFileSync } from "node:fs";
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
function makeCtx() {
  const noop = () => {};
  const grad = { addColorStop: noop };
  return new Proxy({
    canvas: { width: 320, height: 180 },
    createRadialGradient: () => grad,
    createLinearGradient: () => grad,
    measureText: () => ({ width: 4 }),
    getImageData: () => ({ data: new Uint8ClampedArray(4) }),
  }, {
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
  Image: class { set src(_) {} },
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
