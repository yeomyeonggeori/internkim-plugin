---
name: website
description: Create, inspect, edit, preview, publish, or take down dependency-light websites, web apps, prototypes, landing pages, dashboards, and demos.
compatibility: Requires bun, python3, a terminal, and InternKim's tool server.
metadata:
  kim.intern.tool-references: "browser_open browser_snapshot browser_click artifact_review site_serve site_list site_unserve"
---


Command blocks under `references/` write `SKILL_DIR` where this skill's own directory belongs; that directory is `<skill>`.

# Website

Build the site as ordinary files in your own workspace, then hand the finished project to the hosting boundary: `site_serve` previews or publishes a project directory, `site_list` shows what is currently served, `site_unserve` takes a served site down. The server owns the public slug and URL — it allocates them from the title at first serve; you own the files and pick the directory name.

Do not claim production readiness, compliance, SLA, paid hosting, payments, or real integrations unless the user requested and verified them.

## Source and design

User-provided facts are the source of truth. Preserve names, products, people, dates, prices, locations, policies, and confirmation states exactly. Show missing values as the user's-language equivalent of “Not provided”.

Keep a source checklist in `.internkim/required-visible-text.txt` at the project root, one required fact per line. The must-show source content belongs in rendered text, not only metadata or the final reply.

Site text and content live only in `app/public/site-content.json`; never edit `app/src/site-content.ts` (it is the loader code, and touching anything under `app/src/**` forces a full rebuild). `DESIGN.md` at the project root is the design contract: keep its Stitch front matter keys in order (colors, typography, rounded, spacing, components), rewrite the body with this request's actual palette, typeface, and layout decisions, and delete the `TODO(design)` marker — publish-mode serve refuses to ship it.

Use a request-specific visual system. Prefer restrained color, consistent spacing, and meaningful controls. Avoid generic dark navy shells, gradients, decorative filler, placeholder copy, and repeated cards unless the request calls for them.

## Workflow

1. Choose the project root `~/sites/<short-name>/`. The directory name is workspace-only naming you pick; it is not the public slug. Instantiate the managed React, Tailwind, and shadcn scaffold:
   `bash <skill>/scripts/scaffold.sh ~/sites/<short-name> "<site title>"`
   The script refuses a root that already contains `app/` — for a follow-up change, resolve the existing site with `site_list`, then edit the existing project in place instead of scaffolding again.
2. Read existing source before changing it. Fill content in `app/public/site-content.json` only, write the real `DESIGN.md`, and keep the source checklist current. Preserve the content file's existing JSON structure exactly — keep `siteName` and every existing key, edit values in place, and model new sections on an existing one (`references/blocks.md` documents the block shapes); every section needs its `body`. Make small value changes as targeted edits; when edits keep mismatching, read the whole file and write it back complete rather than dropping keys. Never replace the managed scaffold with a scratch project.
3. Build only when you changed anything under `app/` outside `app/public/` (layout, components, styles): `bash <skill>/scripts/build.sh ~/sites/<short-name>`. Content-only sites need no build — the server ships its prebuilt bundle for an unmodified scaffold, so skipping the build is the normal fast path.
4. Validate: `python3 <skill>/scripts/validate.py ~/sites/<short-name>` — it checks the DESIGN.md contract and, when the scaffold structure was modified, a fresh `app/dist` plus the build-quality verdict; it must pass before serving. For an advisory content-quality review, run `python3 <skill>/scripts/content_review.py ~/sites/<short-name>`.
5. Preview: call `site_serve` with `{"title": "<site title>", "sourceWorkspacePath": "~/sites/<short-name>", "mode": "preview"}`. Verify the preview by fetching it: `curl -sL --http1.1 <previewURL>` piped to a text search for each required phrase and control label, plus the content JSON for button labels. A phrase and control present in the fetched preview is complete verification of visibility and presence. If the fetch fails at the transport or edge layer (connection error, tunnel error page such as `error code: 1033`) rather than with a page-level error, verify each required phrase and control label directly in the rendered source files instead (`app/public/site-content.json` plus any edited source), treat that as sufficient verification, and state in the final reply that the live URL could not be fetched from the device network. When browser tools are available, additionally open the preview and click the primary controls; when screenshots exist, run `artifact_review` on them for visual hierarchy and text fit. Fix source with a targeted edit, rebuild when `app/src/**` changed, then preview again.
6. Publish: call `site_serve` in publish mode only after review. Updating a site that is already served means naming the one already there, never guessing or re-deriving a directory name; `site_list` reports both. If serve fails because the directory does not exist, list `~/sites` and retry with the real project directory. Confirm the returned `publishedURL` and `sourceSHA256`.
7. Unserve only when the user explicitly requests taking the site down. Unserve frees the served record and slug but never touches workspace files — remove `~/sites/<short-name>` with `rm -r` only if the user asked for full deletion.

For follow-up edits, resolve the existing site with `site_list` and reuse the identity and path it reports; edit, rebuild, validate, preview, publish. Never create a replacement site for a normal update.

## Final reply

After publish, provide the public URL, what changed, and how to try the main interaction. Identify the result as a prototype when appropriate. Report failures and unfinished review honestly; never fabricate a URL, a verification result, or content the source does not support.
