# SHADOWCOMM Web Console — Modernisation & 3D Plan

A practical plan to make the operator console **simpler, faster, and visibly
bespoke** — 3D where it earns its place, "AI" where it's honest, and none of the
tell-tale generated-design look.

---

## 1. Where the UI stands today

| Aspect | Current |
|---|---|
| Stack | React 19.2 + TypeScript + Vite 8 + Tailwind v4.3 · served by Flask on **5050** |
| Structure | `App.tsx` tab router + `Header` nav; views for messaging, connectivity, devices, security, workstation (10 sub-views), research lab |
| Icons | `lucide-react` ✅ (good choice — already not AI-slop) |
| Bundle | **946 KB JS / 247 KB gzip in one chunk** ⚠️ (warns > 500 KB) |
| Strong points | Real information density, dark tactical palette, honest telemetry ribbon |
| Gaps | Single monolithic bundle; research view only just wired; no spatial/3D representation of the network; motion is minimal |

The foundation is **good**. This is a refinement job, not a rewrite.

---

## 2. Why a page "looks AI-made" — and the specific antidotes

Reviewers and operators read these signals subconsciously. Avoid all of them:

| 🚩 AI tell | ✅ Instead |
|---|---|
| Purple→indigo gradients, glow everywhere | One restrained accent (your existing emerald) on a neutral zinc base |
| Glassmorphism cards + `shadow-xl` on everything | Flat surfaces, 1px borders, shadows only to show elevation/layering |
| Emoji as icons | A single icon set (keep `lucide-react`) at consistent stroke weight |
| Everything `rounded-2xl` and centered | A real 4/8 px spacing scale, left-aligned data, tables that actually align |
| Generic "✨ AI-powered" badges | Name the real model/version and show its measurable output |
| Lorem/placeholder copy, empty states = blank | Purpose-written copy and designed empty states ("No traffic — link standby") |
| Uniform card grids with no hierarchy | Vary weight: critical status large, metadata small and mono |
| Fade-in-on-scroll everywhere | Motion only to explain a state change, 120–200 ms, respects `prefers-reduced-motion` |

The goal: it should read like **mission software** (think a radar console or an
avionics display), not a SaaS marketing site.

---

## 3. Recommended toolkit

### Keep (already in place — don't churn)
- **React 19 + Vite 8 + TypeScript + Tailwind v4** — modern, fast, correct.
- **lucide-react** — consistent icons.

### Add — components & accessibility
| Tool | Why |
|---|---|
| **shadcn/ui** (Radix primitives + Tailwind) | Copy-in, fully editable components — no lock-in, no vendor look. Gets you accessible dialogs/menus/tabs instantly. |
| **Radix UI** directly | If you prefer to own every component. |
| **react-aria** | Best-in-class a11y hooks for custom widgets. |

### Add — 3D & spatial
| Tool | Why |
|---|---|
| **react-three-fiber** + **@react-three/drei** | The React-native way to use Three.js. A 3D link view: Station Alpha ⇄ Bravo with relay nodes as a live topology. |
| **deck.gl** | If you need real geospatial (maps, coverage, bearings) — scales to large overlays. |
| **MapLibre GL** | Free, self-hostable map tiles for node/footprint display. |
| **globe.gl / react-globe.gl** | Quick wins for an "operations globe" without hand-rolling shaders. |

### Add — charts & telemetry
| Tool | Why |
|---|---|
| **uPlot** | Tiny + blazing fast — ideal for live spectrum/BER traces. |
| **visx** or **Recharts** | Structured charts (loss curves, EW statistics battery). |
| **d3** | Bespoke, publication-grade figures for the Research Lab. |

### Add — motion
| Tool | Why |
|---|---|
| **motion** (Framer Motion v11+) | Declarative layout/state animation. |
| CSS transitions | For the 90% case — zero dependency, no bundle cost. |

### Add — typography (biggest single "made-by-a-human" lever)
| Tool | Why |
|---|---|
| **IBM Plex Sans + IBM Plex Mono** | Engineered, non-generic, superb monospace for telemetry. |
| **Geist / Geist Mono** | Modern, clean, less over-used than Inter. |
| **JetBrains Mono** | Excellent for hex/log/WAL dumps. |
| Self-host subsets | No Google Fonts request; faster + privacy. |

> **Rule:** one sans for UI, one mono for *all* numbers/IDs/timestamps. Mixed
> tabular figures are what make a console feel hand-built.

### Add — performance & structure
| Tool | Why |
|---|---|
| **Route/feature code-splitting** (`React.lazy` + `import()`) | Break the 946 KB chunk: lazy-load the Research Lab and 3D views. Biggest perceived-speed win. |
| **`@tanstack/react-query`** | Replaces hand-rolled polling in `MessagesView`; gives caching, retries, background refetch. |
| **Storybook** | Document each console primitive for consistency. |
| **oxlint** (already in `package.json`) | Keep it in CI. |

---

## 4. Concrete plan for *this* console

### Phase A — Split & speed ✅ DONE
1. ✅ `React.lazy` + `<Suspense>` on the heavy views (all workstation labs, Research Lab, Devices, Security, both guided modals, and the 3D topology).
2. ✅ `<Suspense>` fallback is a layout-matched `ViewLoader` (`components/ViewLoader.tsx`), not a bare spinner.
3. ⏳ Move polling to `react-query`; drop manual `setInterval`s. (Still `setInterval` in `App.tsx`.)
4. ⏳ Self-host fonts; set `font-variant-numeric: tabular-nums` on telemetry.

**Measured result (before → after):** single 946 KB bundle → **342 KB initial chunk**
(gzip 94 KB) + per-view chunks (Shell `index-*.js`); the 965 KB three.js engine is now
isolated in the lazy `LinkTopologyView` chunk. Main chunk target (< 300 KB gzip) met with
room to spare.

### Phase B — 3D operational topology ✅ DONE
A **3D Link View** tab (`components/topology/LinkTopologyView.tsx`) built on `react-three-fiber`:
- Two station nodes (Alpha / Bravo), relay nodes, and the active transport as an animated edge.
- Edge colour = link state (emerald online / amber intermittent / red offline), thickness = queue depth.
- Animated packet "comets" along the link, count driven by in-flight message depth.
- Radar sweep ring on the ground plane at Alpha.
- A **Go Live (Motorola)** control in the panel flips the node between the simulated link
  and the radio adapter — the same switch the worker honours (see
  `docs/MOTOROLA_RPI_INTEGRATION.md` §"Switching the node live").
- **Perf rules:** the three.js chunk is lazy-loaded (never on first paint), `<Canvas dpr={[1, 2]}>`,
  and the scene unmounts entirely when another tab is selected.
- **Robustness:** an `ErrorBoundary` degrades the scene to a dependency-free 2D SVG
  schematic (`TopologyFallback.tsx`) if WebGL is unavailable, so the tab is never blank.
- ⏳ Clicking a node opening the message drawer is not yet wired.

### Phase C — Honest "AI" surfaces ✅ DONE
1. ✅ **Model panel** = the real checkpoint, not a chatbot: `ResearchLabView` shows the
   `lpi_v4.best.pt` SHA-256 (`0e8e5153…887c`), epoch, the live compute device (`mps`),
   and the eight-domain EW battery results — the "AI" *is* the model.
2. ✅ **Anomaly surfaces** — per-domain pass/fail is rendered directly as telemetry, and
   the LPI result carries an explicit `error_code` so a failure degrades to
   `UNAVAILABLE` with a reason rather than inventing a number.
3. ⏳ Optional local assistant (`react-query` polling is also still open — Phase A item 3).

### Phase C2 — Waveform Lab ✅ DONE
A dedicated tab (`components/WaveformLabView.tsx` + `components/waveform/WaveformCharts.tsx`)
that puts the **LPI-CGAN** waveform next to a **conventional QPSK** reference, both
measured through the *same* eight-domain EW battery at **matched payload** (128
information bits/frame) and **matched sample budget** (1024 real samples/frame at
245.76 kS/s). Neither column gets a bandwidth or bit-rate advantage, so the
comparison is honest rather than a demo.

Backed by `GET /api/v1/research/waveform-comparison?frames=<1..16>` (default 4),
served by `integration/waveform_lab/service.py`. The conventional track uses the
existing `lpi_research/waveform/baseline.py` generator (64 symbols, sps 8, RRC
roll-off 0.35) — real reference code, not a strawman.

Live result from the current checkpoint:

| Domain (gate) | LPI-CGAN | Conventional QPSK | Flip |
|---|---|---|---|
| KS p-value vs. Gaussian (p > 0.05) | **0.849** ✅ | 3.1e-140 ❌ | yes |
| Kurtosis (\|v−3\| < 0.15) | **2.945** ✅ | 1.465 ❌ | yes |
| Spectral entropy (> 0.95) | **0.958** ✅ | 0.595 ❌ | yes |
| IQ circularity (< 0.15) | **0.014** ✅ | 0.018 ✅ | no |
| PAPR deviation (\|v\| < 3.0) | **−0.10** ✅ | −3.91 ❌ | yes |
| SCF ratio (< 3.0) | **1.018** ✅ | 0.408 ✅ | no |
| HOS C42 (\|v\| < 0.3) | **−0.013** ✅ | −0.776 ❌ | yes |
| WVD ratio (< 3.7) | **1.049** ✅ | 5.624 ❌ | yes |
| **Total** | **8/8** | **2/8** | **6 flip** |

Representative live run. Both tracks draw fresh randomness per call (the generator's
latent `z` and the reference payload bits), so the last digits move run to run; the
result — 8/8 vs 2/8, 6 domains flipping — does not. The page repeats the API's own
disclaimer: these are laboratory statistics from a software model, not a field
guarantee. When the torch checkpoint cannot be loaded the LPI track degrades to
`UNAVAILABLE` **with a reason** (never an invented number) while the numpy-only
conventional track still computes. The view is lazy-loaded into its own ~19.6 KB
chunk. See `docs/PHASE_AUDIT_REPORT.md` and `docs/GROUND_COMMS_DEPLOYMENT.md` §8a.

### Phase D — Design polish
- Lock a **token layer** in Tailwind: one accent, 6 greys, 4 semantic states (ok/warn/crit/info), 4/8 px spacing only.
- Redesign empty/loading/error states with real copy.
- Add a `prefers-reduced-motion` guard around every animation.
- Target **WCAG AA** contrast on all telemetry text.

---

## 5. Quick reference — "good web page" tools by job

| Job | Recommended |
|---|---|
| Framework | React 19 + Vite (keep) · or SvelteKit/Astro for lighter marketing pages |
| Styling | Tailwind v4 (keep) · CSS Modules for bespoke art |
| Components | shadcn/ui · Radix · Ark UI |
| 3D | react-three-fiber + drei · deck.gl · globe.gl |
| Maps | MapLibre GL (free) · Mapbox (paid) |
| Charts | uPlot (live) · visx/Recharts (structured) · d3 (bespoke) |
| Motion | motion (Framer) · CSS transitions |
| State/data | react-query · Zustand (light client state) |
| Icons | lucide-react (keep) · Phosphor |
| Fonts | IBM Plex · Geist · JetBrains Mono (self-hosted) |
| A11y | Radix · react-aria · axe DevTools |
| Perf | Lighthouse · Vite bundle visualiser · Playwright (visual regression) |
| Docs/consistency | Storybook · Chromatic (visual diffs) |

---

## 6. One-line summary

> Keep React+Vite+Tailwind, **code-split the bundle**, add **react-three-fiber**
> for a single purposeful 3D link view, add **shadcn/ui** for accessible
> components, **self-host IBM Plex/Geist** for a hand-built feel, and make the
> "AI" the **real LPI-CGAN model panel** — not a chatbot. Avoid gradients,
> glass, and emoji and it will stop looking generated.

See `docs/PHASE_AUDIT_REPORT.md` for the current build state (frontend compiles
clean; `ResearchLabView` is now reachable via the **Research Lab** nav tab).
