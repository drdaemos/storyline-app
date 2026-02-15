# Frontend Migration Plan: Nuxt UI -> shadcn-vue

## 1. Goal

Migrate the frontend to a cleaner, more controllable UI architecture using `shadcn-vue`, while improving visual quality and keeping the current Vue + Vite foundation.

This document covers:

- Technical assessment of the current frontend implementation.
- Visual/UI shortcomings observed in code and live inspection.
- Proposed target stack.
- Styling system defaults.
- Component migration mapping.
- Phased implementation plan and quality gates.

## 2. Current State Assessment

## 2.1 Stack currently in repo

From `/Users/eugenedementjev/repos/storyline-app/frontend/package.json`:

- Vue 3 + Vite.
- `@nuxt/ui` as primary UI component layer.
- Tailwind CSS v4 syntax (`@import "tailwindcss"` in `/Users/eugenedementjev/repos/storyline-app/frontend/src/assets/main.css`).
- Clerk for auth (`@clerk/vue`) and auth-gated shell rendering.
- Biome lint/format and `vue-tsc` type-checking.

## 2.2 Architecture characteristics

- View components are large and combine UI + interaction + data orchestration:
  - `/Users/eugenedementjev/repos/storyline-app/frontend/src/views/CharacterCreationView.vue` (~960 lines)
  - `/Users/eugenedementjev/repos/storyline-app/frontend/src/views/ScenarioCreationView.vue` (~729 lines)
  - `/Users/eugenedementjev/repos/storyline-app/frontend/src/views/ChatView.vue` (~417 lines)
- Legacy and new backend contracts are mixed in frontend types/composables (`/Users/eugenedementjev/repos/storyline-app/frontend/src/types/index.ts`, `/Users/eugenedementjev/repos/storyline-app/frontend/src/composables/useApi.ts`).
- UI primitives are tightly coupled to `U*` Nuxt UI components across the app.
- Design tokens are minimal and mostly implicit; per-view classes carry most visual decisions.

## 2.3 Live UI findings (Chrome MCP)

Inspected with Chrome MCP on `http://127.0.0.1:3000` (desktop + mobile):

- Current signed-out page is visually sparse and not representative of richer product capabilities.
- Top-level identity exists but overall composition is flat, with large empty space and weak hierarchy.
- Visual language is inconsistent with the planned simulation-heavy workflows.
- Console/network observations:
  - missing favicon (`404`).
  - very broad font loading footprint (multiple font families), which increases style/perf complexity.

Note: authenticated surfaces were not directly visible in the MCP session due auth gating.

## 2.4 Key problems to solve

- UI consistency: repeated ad-hoc class choices, weak shared patterns.
- Maintainability: monolithic views with duplicated interaction patterns.
- Migration readiness: frontend API/type layer lags backend pipeline changes.
- Visual quality: current shell is functional but not design-system-driven.

## 3. Target Stack

Keep:

- Vue 3 + TypeScript + Vue Router.
- Vite build/dev.
- Tailwind v4.
- Clerk auth integration (no auth model change in this migration).

Replace:

- Replace `@nuxt/ui` component layer with `shadcn-vue` components generated into repo.

Add/standardize:

- `shadcn-vue` CLI and local component source (`components/ui/*`).
- Shared utility `cn()` (`clsx` + `tailwind-merge`).
- `class-variance-authority` for predictable component variants.
- `tw-animate-css` for motion primitives.

Official references used:

- [shadcn-vue Vite install](https://www.shadcn-vue.com/docs/installation/vite)
- [shadcn-vue CLI](https://www.shadcn-vue.com/docs/cli)
- [shadcn-vue Tailwind v4 notes](https://www.shadcn-vue.com/docs/tailwind-v4)

## 4. Target Frontend Structure

Recommended structure:

```text
frontend/src/
  app/
    router/
  components/
    ui/                # generated shadcn-vue primitives
    app/               # app-specific composed components
    play/              # play screen blocks
    entities/          # cards, lists, selectors
  composables/
    api/
    stream/
    settings/
  lib/
    utils.ts           # cn()
    design-tokens.ts   # optional token constants for charts/icons/etc
  styles/
    globals.css        # shadcn variables + tailwind imports
```

Guideline:

- Views orchestrate composition only.
- Reusable UI behavior moves into `components/app/*` + composables.
- No business/network logic directly embedded in template-heavy view files.

## 5. Visual System Defaults

## 5.1 Theme direction

Use a neutral, editorial interface suitable for narrative products:

- Base palette: Slate/Stone neutrals.
- Accent: Teal or Amber family (avoid default purple-heavy look).
- Explicit semantic colors for continuation types:
  - `action`: neutral
  - `dialogue`: blue/cyan
  - `relocation`: green
  - `time_skip`: amber

## 5.2 Typography defaults

Use a compact, legible hierarchy:

- UI font: one sans family for controls/content.
- Display font: one serif or contrast family only for major headings.
- Mono font: status, IDs, checks, system metadata.

Avoid loading many font families at once.

## 5.3 Spacing and shape

- 4/8-based spacing scale.
- Card radius: 12px default, 16px for hero blocks.
- Consistent border weight (`1px`) with semantic border tokens.

## 5.4 Elevation and motion

- Elevation via subtle shadow + border contrast.
- Motion defaults:
  - 120-180ms standard transitions.
  - 220-280ms for panel enter/exit.
- Disable decorative motion in reduced-motion mode.

## 5.5 Accessibility defaults

- Color contrast target >= WCAG AA.
- Icon + text labels for status/type badges (never color only).
- Keyboard-visible focus ring system-wide.
- Streamed narration announced with accessible live region strategy.

## 6. shadcn-vue Setup Plan (Existing Project)

Run in `/Users/eugenedementjev/repos/storyline-app/frontend`:

1. Initialize shadcn-vue:

```bash
npm dlx shadcn-vue@latest init
```

2. Add baseline components:

```bash
npm dlx shadcn-vue@latest add button card badge input textarea dialog sheet dropdown-menu tabs separator tooltip skeleton scroll-area sonner
```

3. Ensure styling imports in global CSS:

```css
@import "tailwindcss";
@import "tw-animate-css";
```

4. Define CSS variable tokens from shadcn init output and map brand accents.

5. Keep generated `components.json` committed so future component additions are deterministic.

## 7. Component Migration Mapping

Primary conversions:

- `UButton` -> `Button`
- `UCard` -> `Card`
- `UBadge` -> `Badge`
- `UInput` -> `Input`
- `UTextarea` -> `Textarea`
- `UModal` -> `Dialog`
- `USlideover`/drawer patterns -> `Sheet`
- `USelect` -> `Select` (or searchable `Combobox` where needed)
- `UAlert` -> `Alert`
- `USkeleton` -> `Skeleton`

Chat/play specific:

- Replace `UChat*` dependencies with app-owned play components:
  - `TurnBlock`
  - `NarrationBlock`
  - `ContinuationOptions`
  - `CommandInput`

This prevents lock-in to chat-centric primitives and aligns with turn-based play UX.

## 8. Screen Refactor Strategy

## 8.1 App shell first

Refactor `/Users/eugenedementjev/repos/storyline-app/frontend/src/App.vue` into:

- `AppHeader`
- `PrimaryNav`
- `UserMenu`
- `GlobalToaster`

Use shadcn `NavigationMenu`, `DropdownMenu`, `Sheet` for mobile nav.

## 8.2 Break up large views

Split large views into feature components:

- `CharacterCreationView` -> assistant panel, form sections, save footer.
- `ScenarioCreationView` -> selector panel, narrative panel, action footer.
- `ChatView` (to be replaced by play view) -> turn feed, controls, state drawer.

## 8.3 API/UI boundary cleanup

- Introduce typed API modules by domain (`characters`, `rulesets`, `lore`, `scenarios`, `sessions`, `turns`).
- Normalize SSE events in one place before they reach UI components.
- Remove legacy type fields once backend contract is final.

## 9. Suggested Migration Phases

Phase 0: Prep

- Add shadcn-vue config and base primitives.
- Establish global tokens and typography.

Phase 1: Shell + shared primitives

- Migrate app shell, settings modal, confirm dialogs, basic cards/buttons.

Phase 2: Library/create screens

- Migrate character/scenario creation screens with decomposed components.

Phase 3: Play screen foundation

- Build turn-feed UI using app-owned components and shadcn primitives.

Phase 4: Legacy removal

- Remove `@nuxt/ui`.
- Delete obsolete wrappers and classes.
- Consolidate final style tokens.

## 10. Quality Gates

For each phase:

- `npm run --prefix frontend type-check`
- `npm run --prefix frontend lint`
- `npm run --prefix frontend test:run`

Visual QA checklist:

- Desktop (>=1280), tablet (~768), mobile (~390).
- Dark/light mode.
- Keyboard-only nav and focus visibility.
- Loading/error/empty states for each migrated screen.

## 11. Definition of Done

Migration is complete when:

- `@nuxt/ui` is no longer required.
- Shared design tokens are centralized and used consistently.
- Major screens are composed from reusable `components/ui` + app components.
- Play screen matches turn-based pipeline UX requirements.
- Frontend API types align with backend pipeline endpoints/events.
