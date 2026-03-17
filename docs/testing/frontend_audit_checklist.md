# Frontend audit checklist

Use this when reviewing or auditing the v5 React UI (error handling, a11y, state, and flows).

---

## 1. API and loading

- [ ] Every API call is wrapped in try/catch or `.catch()`; errors are shown in UI (toast, inline message, or error state).
- [ ] Loading states: buttons/forms show loading (disabled + spinner or label) while request is in flight.
- [ ] Empty states: lists (connections, issues, insights, schema) show a clear message when there are no items, not a blank area.
- [ ] Stale data: after mutation (e.g. connect, disconnect, resolve issue), relevant lists/views refresh (refetch or invalidate).

## 2. Forms and validation

- [ ] Sandbox: empty query is prevented or rejected with a clear message (backend enforces; frontend can disable Submit when empty).
- [ ] Simulation: required fields (e.g. table, target rows) are validated; invalid values show inline or toast errors.
- [ ] Connect form: port and numeric fields validated; errors from backend (e.g. connection failed) are shown.
- [ ] Chat: very long input or file count limits (if any) are communicated or enforced.

## 3. Connection and context

- [ ] When no connection is active, pages that need a DB (Query, Sandbox, Simulation, etc.) show a clear “Connect first” or similar.
- [ ] Connection selector (if present) is in sync with backend; switching connection updates schema/health/context where needed.
- [ ] After backend restart, chat/session state is cleared or revalidated (instance_id / session validate behavior).

## 4. Accessibility (a11y)

- [ ] Main nav and key actions are keyboard-focusable and have visible focus style.
- [ ] Forms: inputs have associated labels (or `aria-label`); errors are associated (e.g. `aria-describedby` or live region).
- [ ] Buttons and links have descriptive text or `aria-label` (e.g. “Run query”, “Send message”).
- [ ] Color is not the only way to convey status (e.g. health/severity also has text or icons).

## 5. Routes and deep links

- [ ] All main routes load without crash: `/`, `/query`, `/health`, `/issues`, `/sandbox`, `/chat`, `/graph`, `/insights`, `/simulation`, `/connections`.
- [ ] Chat `?prefill=...` is applied when present (e.g. from Issues “Fix” button).

## 6. Real-time and WebSocket

- [ ] WebSocket connect/reconnect does not cause duplicate subscriptions or repeated full refetches where avoidable.
- [ ] When WS is used for issues/health, UI updates (e.g. issue list, health badges) after events.

## 7. Build and types

- [ ] `npm run build` passes (TypeScript strict, no `any` or `unknown` used as ReactNode without narrowing).
- [ ] No console errors or warnings in normal flows (dev and production build).

---

## Quick verification commands

```bash
# From v5/frontend
npm run build

# From v5/tests/e2e (with backend + frontend running)
npm install && npx playwright install chromium && npm test
```

Mark items as you complete them and note any bugs or follow-ups in `tasks/todo.md` or `tasks/lessons.md`.
