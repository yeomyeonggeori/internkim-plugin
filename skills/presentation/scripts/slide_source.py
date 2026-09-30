import re


SPEAKER_NOTES_BLOCK_PATTERN = (
    r"<(?:aside|div)\b[^>]*class=[\"'][^\"']*(?:speaker-notes|notes)[^\"']*[\"'][^>]*>(.*?)</(?:aside|div)>"
)


def split_slide_sources(source_text: str) -> list[str]:
    sections = re.findall(r"<section\b[^>]*>.*?</section>", source_text, flags=re.IGNORECASE | re.DOTALL)
    return [section.strip() for section in sections if section.strip()]


def remove_invisible_markup(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(SPEAKER_NOTES_BLOCK_PATTERN, " ", text, flags=re.DOTALL | re.IGNORECASE)
