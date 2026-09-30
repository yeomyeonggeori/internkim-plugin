# Paperlogy Font Assets

These files are vendored from `fonts-archive/Paperlogy` for deterministic slide rendering.

- `Paperlogy-4Regular.woff2`, `Paperlogy-4Regular.ttf`: 400
- `Paperlogy-6SemiBold.woff2`, `Paperlogy-6SemiBold.ttf`: 600
- `Paperlogy-7Bold.woff2`, `Paperlogy-7Bold.ttf`: 700
- `Paperlogy-8ExtraBold.woff2`, `Paperlogy-8ExtraBold.ttf`: 800

The browser loads the WOFF2 files. The TTF files hold the same tables uncompressed and are embedded into the PPTX, because the system Python that builds a deck cannot decompress WOFF2.

Paperlogy is distributed under the SIL Open Font License 1.1. The license text is included in `OFL-1.1.txt`.
