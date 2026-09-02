# Block Capabilities Reference

## Icons

`features` and `contact` items accept an `icon` field with one of these lucide names; anything else falls back to a numbered index:

award, book-open, calendar, check-circle, clock, coffee, compass, flame, gift, globe, hammer, heart, instagram, leaf, lightbulb, mail, map-pin, message-circle, package, palette, phone, rocket, shield-check, shopping-bag, sparkles, star, sun, users, wrench, zap

Choose icons that match each item's meaning: contact items usually pair `mail`, `instagram`, `map-pin`, `clock`; feature grids pick per-item metaphors. Do not decorate every block — icons carry meaning, not garnish.

## Images

`hero` and `prose` blocks accept `image` (path or URL) plus `imageAlt`. A hero with an image renders text-left, image-right; a prose image renders as a wide banner above the text.

Sourcing order:
1. Files the user attached or that already exist in the site workspace.
2. One command fetches a CC0/public-domain photo — search, license filter, download, and the reference path in one step:

   ```
   python3 <skill>/scripts/fetch_image.py "pottery hands clay wheel" app/public/images/hero.jpg
   ```

   Query in simple English; the script prints the `/images/...` path to use. Prototype images are placeholders the user can later replace with real photos through a normal update request.
3. Image generation skills, only when no suitable photo exists (abstract brand art, products that do not exist yet).

Always set `imageAlt`. Keep files under about 400KB; prefer 1600px-wide JPEG.

## Contact Links

Contact body text and item bodies auto-link emails (mailto:), full URLs, and @instagram handles — write them as plain text like `hello@example.com`, `https://example.com`, `@studio.handle`, and the renderer makes them clickable. Use contact `items` for structured entries: `{ "title": "이메일", "body": "hello@example.com", "icon": "mail" }`.

## Backdrops

`hero` and `cta` blocks accept `backdrop` with one of: `mesh`, `aurora`, `grain`, `grid`, `dots`. Each renders a designer-grade decorative layer from the theme palette — no image needed, colors always harmonize:

- `mesh`: blended multi-point color gradient; warm, contemporary hero default.
- `aurora`: large soft blurred color fields; dreamy, premium.
- `grain`: film-grain texture over a soft tint; crafted, analog.
- `grid`: fine fading line grid; technical, product-focused.
- `dots`: fading dot matrix; playful, precise.

A hero with no image should almost always carry a backdrop that matches the mood. Combine with the `style:` preset in DESIGN.md — e.g. pottery studio: `grain`; tech product: `grid` or `mesh`; kids brand: `dots`.

## Font Catalog

Served families (anything else silently falls back to the platform default): `에이투지체` (default; all-round geometric sans), `Pretendard` (neutral body/UI), `Paperlogy` (display-friendly geometric), `마루부리` (screen serif with brush warmth), `Gowun Batang` (quiet literary serif), `Gowun Dodum` (handwritten-humanist), `Galmuri` (retro pixel), `D2Coding` (mono). Match the voice to the request and say why in DESIGN.md.

## Auth (membership)

Most sites need no auth — add it only when the request has genuinely member-only content, never as decoration. When it does, declare at the manifest top level:

```json
"auth": {"enabled": true}
```

and mark member-only pages with `"access": "authenticated"`. The runtime then provides `/login` and `/signup` pages (email + password, PocketBase-backed), a session-aware navigation entry, and redirects visitors from protected pages to login. Optional keys: `userCollection` (default `users`), `allowSignup` (default true), `loginPath`, `signupPath`, `redirectAfterLogin`, and `providers` (e.g. `["google", "kakao"]` — renders social login buttons; works only after an administrator registers that provider's OAuth keys outside the chat, so declare providers only when the user says they are configured). Do not build custom login forms or fake auth with prose blocks.
