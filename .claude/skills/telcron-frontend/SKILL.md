---
name: telcron-frontend
description: How Telcron's React app is built — the testlabhub.com look, design tokens, the API client, auth, page states and phone layout. Load before writing or changing any page or component.
---

# Frontend

The look follows **https://testlabhub.com** (a Telcron property): white header with the wordmark and uppercase
navigation, an indigo pill "Sign In", a deep maroon hero with a large light headline and a search box,
pink-tinted rounded cards with dark-red headings, pale rounded panels for sections, Poppins throughout. That
site is client-rendered: read it with a real browser, a plain fetch returns an empty shell.

- **Tokens only.** Colours and the font are defined once in `src/index.css` under `@theme`
  (`brand`, `brand-ink`, `brand-tint`, `action`, `panel`, `warm`, `ok`, `warn`, `danger`, ...). No hex or
  literal colour in a component. Shared classes: `container-page`, `btn`, `btn-ghost`, `field`, `card`, `eyebrow`.
- **One API client.** Everything goes through `src/lib/api.ts` (`api`, `post`). It attaches the token, refreshes
  once on a 401 (a single shared refresh, because refresh tokens rotate) and throws `ApiError` with the server's
  code. Add the code to `MESSAGES` so `explain()` can say what to do next.
- **Load data with `useLoad`** and design all four states: loading, empty (with a way forward), error, loaded.
- **Auth** is `useAuth()`. Members-only pages wrap their body in `Gate` (`pages/Member.tsx`), which offers
  sign-in instead of showing an error.
- **Phone first.** Check 390 px: no horizontal scroll, the menu collapses, tap targets are finger-sized.
- Semantic HTML, a label on every input, `role="alert"` on errors, visible focus.
- The Telcron logo image is not in the repo yet; the header uses a text wordmark until the asset is supplied.
- A new page is reported to `tech-lead`, who adds the route and the navigation entry.

Verify in a browser before reporting: `npm run dev` in `frontend/`, walk the flow, look at the console.
