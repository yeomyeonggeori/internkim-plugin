#!/usr/bin/env python3
import datetime
import json
import pathlib
import re
import sys

CONTENT_GATE_SCORE_MINIMUM = 82
WARNING_WEIGHTS = {
    "missingRequiredTextWarning": 16,
    "numberedFillerWarning": 14,
    "emptyBlockTextWarning": 12,
    "repeatedVariantWarning": 10,
    "heroPlacementWarning": 10,
    "languageMismatchWarning": 10,
    "unsourcedCurrentDateWarning": 10,
    "emojiIconWarning": 8,
    "missingDesignDocumentWarning": 12,
    "thinPageWarning": 10,
    "blockRhythmWarning": 8,
    "sparseItemsWarning": 8,
    "duplicatedPageCompositionWarning": 8,
    "defaultPaletteWarning": 10,
    "genericFontWarning": 8,
    "bareHeroWarning": 6,
    "escapedNewlineWarning": 10,
    "pipeDelimitedBodyWarning": 8,
    "iconConsistencyWarning": 6,
    "deadContactWarning": 19,
    "unknownBackdropWarning": 10,
    "hotlinkedImageWarning": 19,
    "missingImageryWarning": 8,
    "referencedImageMissingWarning": 19,
}
KNOWN_BACKDROPS = {"mesh", "aurora", "grain", "grid", "dots"}
GENERIC_FONT_KEYWORDS = {
    "ui-sans-serif", "ui-serif", "ui-monospace", "ui-rounded", "system-ui",
    "sans-serif", "serif", "monospace", "cursive", "fantasy",
}
HANGUL_PATTERN = re.compile(r"[가-힣]")
LATIN_LETTER_PATTERN = re.compile(r"[A-Za-z]")
EMOJI_PATTERN = re.compile("[\U0001F000-\U0001FAFF✅❌❎❗❓⭐⚠⌚⏰️]")


def locate_source_root(candidate: pathlib.Path) -> pathlib.Path:
    probe = candidate.resolve()
    for _ in range(6):
        if (probe / "app" / "public" / "site-content.json").exists():
            return probe
        if probe.name == "app" and (probe / "public" / "site-content.json").exists():
            return probe.parent
        probe = probe.parent
    return candidate


def main() -> int:
    source_root = locate_source_root(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("."))
    content_path = source_root / "app" / "public" / "site-content.json"
    if not content_path.exists():
        print(f"Error: {content_path} not found; run from the source workspace root or pass it as the argument.")
        return 2
    try:
        content = json.loads(content_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"Content review FAILED: site-content.json is not valid JSON: {error}")
        return 0
    pages = content.get("pages") or []
    blocks = [block for page in pages for block in page.get("blocks") or []] or content.get("blocks") or []
    visible_text = collect_visible_text(content, blocks)
    for page in pages:
        visible_text += "\n" + str(page.get("title") or "")
    ledger_text = read_optional(source_root / ".internkim" / "required-visible-text.txt")
    warnings = []
    warnings += required_text_warnings(visible_text, ledger_text)
    warnings += numbered_filler_warnings(blocks)
    warnings += empty_text_warnings(blocks)
    if pages:
        for page in pages:
            warnings += variant_structure_warnings(page.get("blocks") or [])
    else:
        warnings += variant_structure_warnings(blocks)
    warnings += language_warnings(blocks, visible_text)
    warnings += current_date_warnings(visible_text, ledger_text)
    warnings += emoji_warnings(visible_text)
    warnings += design_document_warnings(source_root)
    warnings += page_structure_warnings(pages, blocks)
    if "\\n" in visible_text:
        warnings.append("escapedNewlineWarning: rendered text contains a literal backslash-n; write real newlines inside JSON strings")
    warnings += design_intent_warnings(source_root)
    warnings += dead_contact_warnings(pages, blocks)
    for page_path, block_index, image in ((page.get("path") or "/", index, str(block.get("image") or "")) for page in pages for index, block in enumerate(page.get("blocks") or [])):
        if not image.startswith("/"):
            continue
        expected = source_root / "app" / "public" / image.lstrip("/")
        if expected.exists():
            continue
        stray = list(source_root.rglob(pathlib.Path(image).name))
        hint = f"; a file with that name sits at {stray[0].relative_to(source_root)} — move it to app/public{image}" if stray else ""
        warnings.append(f"referencedImageMissingWarning: page {page_path} block {block_index} references {image} but app/public{image} does not exist{hint}")
    if not any(block.get("image") for block in blocks):
        warnings.append("missingImageryWarning: no photography anywhere on the site — visitors expect at least a hero image; fetch a CC0 photo with scripts/fetch_image.py \"<english query>\" app/public/images/<name>.jpg (skip only for an intentionally text-only look)")
    score = max(0, 100 - sum(WARNING_WEIGHTS.get(warning.split(":")[0], 6) for warning in warnings))
    verdict = "PASSED" if score >= CONTENT_GATE_SCORE_MINIMUM else "FAILED"
    print(f"Content review: {len(blocks)} blocks, score {score}/100 (minimum {CONTENT_GATE_SCORE_MINIMUM})")
    if warnings:
        print(f"Content gate {verdict}. Resolve these before publish-mode site_serve:" if verdict == "FAILED" else f"Content gate {verdict} with notes:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("Content gate PASSED.")
    for note in unused_palette_notes(blocks):
        print(f"  ~ {note}")
    return 0


def unused_palette_notes(blocks: list) -> list:
    notes = []
    has_items = any(block.get("items") for block in blocks)
    has_icons = any(item.get("icon") for block in blocks for item in block.get("items") or [])
    if has_items and not has_icons:
        notes.append("palette: items accept icon (mail, instagram, map-pin, calendar, clock, flame, leaf, star, heart, users, sparkles, palette, hammer, coffee, sun, gift, award, compass, ... full list in references/blocks.md) when meaning calls for it")

    has_backdrops = any(str(block.get("backdrop") or "") for block in blocks)
    if not has_backdrops:
        notes.append("palette: hero/cta accept backdrop — mesh (blended color field), aurora (soft glow), grain (analog texture), grid (technical lines), dots (playful matrix)")
    return notes


def collect_visible_text(content: dict, blocks: list) -> str:
    parts = [str(content.get("siteName") or ""), str(content.get("tagline") or "")]
    for block in blocks:
        parts += [str(block.get("title") or ""), str(block.get("body") or ""), str(block.get("actionLabel") or "")]
        for item in block.get("items") or []:
            parts += [str(item.get("title") or ""), str(item.get("body") or "")]
    return "\n".join(part for part in parts if part)


def read_optional(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def required_text_warnings(visible_text: str, ledger_text: str) -> list:
    lines = [line.strip() for line in ledger_text.splitlines() if line.strip()]
    if not lines:
        return []
    haystack = normalize(visible_text)
    spaceless = haystack.replace(" ", "")
    missing = [
        line for line in lines
        if normalize(line) not in haystack and normalize(line).replace(" ", "") not in spaceless
    ]
    if not missing:
        return []
    preview = "; ".join(missing[:4]) + (" ..." if len(missing) > 4 else "")
    return [f"missingRequiredTextWarning: {len(missing)} of {len(lines)} required-visible-text.txt lines are not in the rendered text: {preview}"]


def numbered_filler_warnings(blocks: list) -> list:
    warnings = []
    for index, block in enumerate(blocks, start=1):
        stems = []
        for item in block.get("items") or []:
            title = str(item.get("title") or "").strip()
            stem = re.sub(r"[\s\-#.]*\d+$", "", title).strip()
            if stem and stem != title:
                stems.append(stem.casefold())
        counted = {stem: stems.count(stem) for stem in stems}
        if any(count >= 2 for count in counted.values()):
            warnings.append(f"numberedFillerWarning: block {index} items are the same title with a trailing number; write real content for each item")
    return warnings


def empty_text_warnings(blocks: list) -> list:
    empty_indexes = []
    for index, block in enumerate(blocks, start=1):
        texts = [str(block.get("title") or ""), str(block.get("body") or "")]
        texts += [str(item.get("title") or "") + str(item.get("body") or "") for item in block.get("items") or []]
        if not any(text.strip() for text in texts):
            empty_indexes.append(str(index))
    if empty_indexes:
        return ["emptyBlockTextWarning: block " + ", ".join(empty_indexes) + " has no visible text"]
    return []


def variant_structure_warnings(blocks: list) -> list:
    warnings = []
    variants = [str(block.get("variant") or "") for block in blocks]
    hero_positions = [index for index, variant in enumerate(variants) if variant == "hero"]
    if hero_positions and (hero_positions[0] != 0 or len(hero_positions) > 1):
        warnings.append("heroPlacementWarning: use exactly one hero block and place it first")
    for variant in set(variants):
        if variant and variant != "hero" and variants.count(variant) >= 3:
            warnings.append(f"repeatedVariantWarning: the {variant} variant appears {variants.count(variant)} times; vary the block sequence")
    return warnings


def language_warnings(blocks: list, visible_text: str) -> list:
    hangul_count = len(HANGUL_PATTERN.findall(visible_text))
    latin_count = len(LATIN_LETTER_PATTERN.findall(visible_text))
    if hangul_count < 40 or hangul_count * 3 < latin_count:
        return []
    mismatched = [
        str(index)
        for index, block in enumerate(blocks, start=1)
        if title_is_latin_only(str(block.get("title") or ""))
    ]
    if mismatched:
        return ["languageMismatchWarning: block " + ", ".join(mismatched) + " titles are Latin-only while the site text is Korean"]
    return []


def title_is_latin_only(title: str) -> bool:
    return len(LATIN_LETTER_PATTERN.findall(title)) >= 4 and not HANGUL_PATTERN.search(title)


def current_date_warnings(visible_text: str, ledger_text: str) -> list:
    today = datetime.date.today()
    separator = r"\s*[.\-/년월]\s*"
    pattern = re.compile(rf"(?<!\d){today.year}{separator}0?{today.month}{separator}0?{today.day}(?!\d)")
    if pattern.search(ledger_text) or not pattern.search(visible_text):
        return []
    return [f"unsourcedCurrentDateWarning: the rendered text shows today's date {today.isoformat()}, which is not in required-visible-text.txt"]


def emoji_warnings(visible_text: str) -> list:
    if EMOJI_PATTERN.search(visible_text):
        return ["emojiIconWarning: rendered text uses emoji glyphs; use plain labels or the scaffold's icons"]
    return []


def page_structure_warnings(pages: list, all_blocks: list) -> list:
    warnings = []
    page_entries = [(str(page.get("path") or f"#{index}"), page.get("blocks") or []) for index, page in enumerate(pages, start=1)]
    if not page_entries:
        page_entries = [("/", all_blocks)]
    compositions = {}
    for path_label, blocks in page_entries:
        variants = [str(block.get("variant") or "") for block in blocks]
        page_text = collect_visible_text({}, blocks)
        if len(blocks) == 1 and len(page_text) < 220 and variants[0] not in ("contact", "cta"):
            warnings.append(f"thinPageWarning: page {path_label} is a single block with little text; add supporting blocks or depth")
        for position in range(len(variants) - 2):
            if variants[position] == variants[position + 1] == variants[position + 2]:
                warnings.append(f"blockRhythmWarning: page {path_label} repeats the {variants[position]} variant three times in a row; vary the rhythm")
                break
        signature = ">".join(variants)
        if len(variants) >= 2 and signature in compositions:
            warnings.append(f"duplicatedPageCompositionWarning: pages {compositions[signature]} and {path_label} share the exact block sequence; give each page its own composition")
        compositions.setdefault(signature, path_label)
        for block_index, block in enumerate(blocks, start=1):
            variant = str(block.get("variant") or "")
            items = block.get("items") or []
            if variant in ("features", "faq") and len(items) == 1:
                warnings.append(f"sparseItemsWarning: page {path_label} block {block_index} is a {variant} with a single item; use a different variant or add real items")
            image_value = str(block.get("image") or "").strip()
            if image_value.startswith("http://") or image_value.startswith("https://"):
                warnings.append(f"hotlinkedImageWarning: page {path_label} block {block_index} hotlinks an external image whose subject and availability cannot be trusted; fetch a CC0 photo with scripts/fetch_image.py into app/public/images/ and reference /images/<name>")
            backdrop = str(block.get("backdrop") or "").strip()
            if backdrop and backdrop not in KNOWN_BACKDROPS:
                warnings.append(f"unknownBackdropWarning: page {path_label} block {block_index} backdrop {backdrop!r} does not exist and renders as nothing; choose mesh, aurora, grain, grid, or dots")
            if variant == "hero" and not block.get("image") and backdrop not in KNOWN_BACKDROPS:
                warnings.append(f"bareHeroWarning: page {path_label} hero has neither image nor backdrop; add a backdrop (mesh, aurora, grain, grid, dots) or an image")
            icon_flags = [bool(str(item.get("icon") or "").strip()) for item in items]
            if any(icon_flags) and not all(icon_flags):
                warnings.append(f"iconConsistencyWarning: page {path_label} block {block_index} splits the grammar of same-level cards; give every item an icon or none")
            for item_index, item in enumerate(items, start=1):
                body_text = str(item.get("body") or "")
                if " | " in body_text or body_text.count("|") >= 2:
                    warnings.append(f"pipeDelimitedBodyWarning: page {path_label} block {block_index} item {item_index} crams scannable specs into a sentence; give data structure with line breaks or separate labeled items")
                    break
    return warnings


CONTACT_REACHABLE_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|https?://\S+|(?<![\w.])@[\w.]{2,30}")


def dead_contact_warnings(pages: list, all_blocks: list) -> list:
    page_entries = [(str(page.get("path") or ""), page.get("blocks") or []) for page in pages] or [("/", all_blocks)]
    warnings = []
    for path_label, blocks in page_entries:
        for block in blocks:
            if str(block.get("variant") or "") != "contact":
                continue
            contact_text = collect_visible_text({}, [block])
            if not CONTACT_REACHABLE_PATTERN.search(contact_text):
                warnings.append(f"deadContactWarning: page {path_label} contact block gives visitors no way to actually reach anyone; include an email, URL, or handle so it links")
    return warnings


def design_intent_warnings(source_root: pathlib.Path) -> list:
    design_text = read_optional(source_root / "DESIGN.md")
    if not design_text.startswith("---"):
        return []
    front_matter = design_text.split("---", 2)[1]
    warnings = []
    primary = (re.search(r"primary:\s*\"?(#[0-9a-fA-F]{3,6})", front_matter) or [None, ""])[1].lower()
    background = (re.search(r"background:\s*\"?(#[0-9a-fA-F]{3,6})", front_matter) or [None, ""])[1].lower()
    has_style_preset = bool(re.search(r"(?m)^style\s*:", front_matter))
    if primary in ("#111111", "#000000", "#111") and background in ("#ffffff", "#fff") and not has_style_preset:
        warnings.append("defaultPaletteWarning: colors are the template default black-on-white with no style preset; choose a palette and style that fit this request")
    font_families = re.findall(r"fontFamily:\s*\"?([^\"\n]+)", front_matter)
    generic = [family.strip().strip("\"'") for family in font_families if family.strip().strip("\"'").lower() in GENERIC_FONT_KEYWORDS]
    if generic:
        warnings.append(f"genericFontWarning: typography uses generic keyword families ({', '.join(sorted(set(generic)))}); pick a catalog typeface that matches the request")
    return warnings


def design_document_warnings(source_root: pathlib.Path) -> list:
    design_text = read_optional(source_root / "DESIGN.md")
    body = design_text.split("---", 2)[2].strip() if design_text.startswith("---") and design_text.count("---") >= 2 else design_text.strip()
    if len(body) >= 80:
        return []
    return ["missingDesignDocumentWarning: DESIGN.md at the source root is missing or does not describe the design beyond front matter"]


if __name__ == "__main__":
    raise SystemExit(main())
