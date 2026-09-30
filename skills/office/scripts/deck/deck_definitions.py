from dataclasses import dataclass

from office_result import ERROR, WARNING, Issue, IssueKind


DECK_LOCATION = "deck"


@dataclass(frozen=True)
class ReviewCheck:
    kind: IssueKind
    label: str = ""
    weight: int = 0

    def issue(self, text: str, location: str | None = None) -> Issue:
        message = f"{self.label}: {text}" if self.label else text
        return self.kind.issue(message, location)

    def deck_issue(self, text: str) -> Issue:
        return self.issue(text, DECK_LOCATION)


def review_check(code: str, meaning: str, suggestion: str, label: str = "", weight: int = 0) -> ReviewCheck:
    return ReviewCheck(IssueKind(code, WARNING, meaning, suggestion), label, weight)


SLIDE_BLANK = review_check("SLIDE_BLANK", "the slide render shows no content", "check that the slide's content is not hidden or outside the frame")
SAFE_MARGIN_INTRUSION = review_check("SAFE_MARGIN_INTRUSION", "content reaches inside the DESIGN.md safe margin", "pull content back inside layout.margin")
EDGE_CLIPPING = review_check("EDGE_CLIPPING", "content touches the slide edge", "keep content off the frame edge so nothing is clipped")
SLIDE_TOO_SPARSE = review_check("SLIDE_TOO_SPARSE", "the slide is nearly empty", "give the slide enough content to justify it, or merge it")
SLIDE_TOO_CROWDED = review_check("SLIDE_TOO_CROWDED", "the slide is visually crowded", "cut or split the content")
CONTENT_OVERFLOW = review_check("CONTENT_OVERFLOW", "an element's content is larger than its box, so it is clipped or spills out", "enlarge the box, cut the content, or lower the type size")
OUT_OF_FRAME = review_check("OUT_OF_FRAME", "an element lies partly or wholly outside its slide", "move or resize the element so it sits inside the slide")
TEXT_OVERLAP = review_check("TEXT_OVERLAP", "two pieces of text cover each other", "separate the two text blocks or shorten the one that spills")
IMAGE_DISTORTED = review_check("IMAGE_DISTORTED", "an image is stretched away from its own aspect ratio", "set object-fit: cover or contain, or size the image to its ratio")
GEOMETRY_NOT_MEASURED = review_check("GEOMETRY_NOT_MEASURED", "no browser measured element geometry, so overflow, overlap and stretched images were not checked", "rerun the build where a browser renders the deck, or say the layout was not measured")
FRAME_FIT_RISK = review_check("FRAME_FIT_RISK", "content is close to the right or bottom frame edge", "check the contact sheet for clipped text", label="frameFitRisk")
UNRELIABLE_VISUAL_EVIDENCE = review_check("UNRELIABLE_VISUAL_EVIDENCE", "review images did not come from a browser", "treat the previews as approximate and say so when delivering", label="unreliableVisualEvidenceWarning")

WEAK_VISUAL_IDENTITY = review_check("WEAK_VISUAL_IDENTITY", "the deck declares no visual system", "add data-visual-system to slides.html and describe the system in DESIGN.md", "weakVisualIdentityWarning", 24)
MISSING_SLIDE_ROLE = review_check("MISSING_SLIDE_ROLE", "a slide lacks data-slide-role", "give every slide section a data-slide-role", "missingSlideRoleWarning", 16)
SIDE_STRIPE = review_check("SIDE_STRIPE", "thick side border accents carry the visual identity", "carry the identity through composition, type, and color instead", "sideStripeWarning", 14)
GHOST_CARD = review_check("GHOST_CARD", "thin-bordered soft-shadow boxes read as a default template", "replace them with the deck's own surfaces", "ghostCardWarning", 14)
TINY_TEXT = review_check("TINY_TEXT", "several CSS font sizes are below 16px", "raise text to at least 16px", "tinyTextWarning", 8)
REPEATED_COMPOSITION = review_check("REPEATED_COMPOSITION", "three or more slides share one composition", "vary slide composition by role", "repeatedCompositionWarning", 14)
RAW_STRUCTURE_PATTERN = review_check("RAW_STRUCTURE_PATTERN", "several slides are a raw table or bare list", "turn the tables and lists into designed compositions", "rawStructurePatternWarning", 12)
RAW_TABLE = review_check("RAW_TABLE", "a raw table is the slide's main composition", "design the comparison instead of dropping in a table", "rawTableWarning", 10)
BARE_LIST = review_check("BARE_LIST", "a bare list is the slide's main composition", "design the points instead of listing them", "bareListWarning", 10)
TOPIC_TITLE = review_check("TOPIC_TITLE", "the title is a topic label, not a claim", "write the title as the slide's conclusion", "topicTitleWarning", 8)
LANGUAGE_MISMATCH = review_check("LANGUAGE_MISMATCH", "slide titles are Latin-only in a Korean deck", "write the titles in the request language", "languageMismatchWarning", 10)
UNSOURCED_CURRENT_DATE = review_check("UNSOURCED_CURRENT_DATE", "a slide shows today's date that the source does not", "show only dates from the source material", "unsourcedCurrentDateWarning", 10)
VERTICAL_DEAD_ZONE = review_check("VERTICAL_DEAD_ZONE", "an empty band spans much of the slide height", "distribute content to fill the frame", "verticalDeadZoneWarning", 10)
ABSOLUTE_FOOTER = review_check("ABSOLUTE_FOOTER", "an absolutely positioned bottom strip carries text", "make header, body, and footer sibling flow children", "absoluteFooterWarning", 12)
EMOJI_ICON = review_check("EMOJI_ICON", "a slide uses emoji glyphs", "use text labels, CSS markers, or inline SVG", "emojiIconWarning", 8)
MISSING_REQUIRED_TEXT = review_check("MISSING_REQUIRED_TEXT", "required-visible-text.txt lines are not visible", "put every required line on a slide", "missingRequiredTextWarning", 14)
INCONSISTENT_FOOTER_BASELINE = review_check("INCONSISTENT_FOOTER_BASELINE", "the content bottom edge varies across slides", "keep the footer on one baseline", "inconsistentFooterBaselineWarning", 8)
UNPINNED_FOOTER = review_check("UNPINNED_FOOTER", "the recurring footer is not pinned to the frame bottom", "give it margin-top: auto inside the flex column slide", "unpinnedFooterWarning", 10)
MISSING_SPEAKER_NOTES = review_check("MISSING_SPEAKER_NOTES", "a slide has no speaker notes", 'add an <aside class="notes"> script to every slide', "missingSpeakerNotesWarning", 8)

SLIDE_RENDER_CHECKS = (SLIDE_BLANK, SAFE_MARGIN_INTRUSION, EDGE_CLIPPING, SLIDE_TOO_SPARSE, SLIDE_TOO_CROWDED, CONTENT_OVERFLOW, OUT_OF_FRAME, TEXT_OVERLAP, IMAGE_DISTORTED, GEOMETRY_NOT_MEASURED, FRAME_FIT_RISK, UNRELIABLE_VISUAL_EVIDENCE)
DESIGN_CHECKS = (
    WEAK_VISUAL_IDENTITY,
    MISSING_SLIDE_ROLE,
    SIDE_STRIPE,
    GHOST_CARD,
    TINY_TEXT,
    REPEATED_COMPOSITION,
    RAW_STRUCTURE_PATTERN,
    RAW_TABLE,
    BARE_LIST,
    TOPIC_TITLE,
    LANGUAGE_MISMATCH,
    UNSOURCED_CURRENT_DATE,
    VERTICAL_DEAD_ZONE,
    ABSOLUTE_FOOTER,
    EMOJI_ICON,
    MISSING_REQUIRED_TEXT,
    INCONSISTENT_FOOTER_BASELINE,
    UNPINNED_FOOTER,
    MISSING_SPEAKER_NOTES,
)
DESIGN_WARNING_WEIGHTS = {check.kind.code: check.weight for check in DESIGN_CHECKS}
REVIEW_ISSUE_KINDS = tuple(check.kind for check in SLIDE_RENDER_CHECKS + DESIGN_CHECKS)

SOURCE_NOT_HTML = IssueKind("SOURCE_NOT_HTML", ERROR, "the deck source is not an .html file", "write slides.html, or set SRC to an .html file")
NO_SLIDE_SECTIONS = IssueKind("NO_SLIDE_SECTIONS", ERROR, "the HTML has no <section> slides", "put each slide in its own <section>")
UNKNOWN_FORMAT = IssueKind("UNKNOWN_FORMAT", ERROR, "FORMATS names a format the build cannot write", "use html, pdf, pptx, notes, review, or all")
REVIEW_FAILED = IssueKind("REVIEW_FAILED", ERROR, "the slide review stopped before writing its report", "read the review's error output above the result")
DESIGN_DOCUMENT_MISSING = IssueKind("DESIGN_DOCUMENT_MISSING", WARNING, "DESIGN.md is absent beside the source", "write DESIGN.md before building")
DESIGN_SOURCE_MARKER_MISSING = IssueKind("DESIGN_SOURCE_MARKER_MISSING", WARNING, "the source does not name design-source: DESIGN.md", "add the design-source: DESIGN.md comment to the source")
DECK_BRIEF_MISSING = IssueKind("DECK_BRIEF_MISSING", WARNING, "deck-brief.md is absent, so the slide count is not cross-checked", "write deck-brief.md with the requested slide count")
REQUIRED_TEXT_LEDGER_MISSING = IssueKind("REQUIRED_TEXT_LEDGER_MISSING", WARNING, "required-visible-text.txt is absent, so source facts are not checked", "list the source facts in required-visible-text.txt")
SLIDE_COUNT_MISMATCH = IssueKind("SLIDE_COUNT_MISMATCH", WARNING, "the slide count differs from deck-brief.md", "fix slides.html if the user asked for an exact count; otherwise update deck-brief.md")
BROWSER_RENDER_UNAVAILABLE = IssueKind("BROWSER_RENDER_UNAVAILABLE", WARNING, "no browser rendered the deck", "say that the PDF and screenshots are missing, or deliver from a host with a browser")
IMAGE_PPTX_UNAVAILABLE = IssueKind("IMAGE_PPTX_UNAVAILABLE", WARNING, "the PPTX holds native text slides because no slide images were rendered", "say the PPTX is the native fallback when delivering it")

BUILD_ISSUE_KINDS = (
    SOURCE_NOT_HTML,
    NO_SLIDE_SECTIONS,
    UNKNOWN_FORMAT,
    REVIEW_FAILED,
    DESIGN_DOCUMENT_MISSING,
    DESIGN_SOURCE_MARKER_MISSING,
    DECK_BRIEF_MISSING,
    REQUIRED_TEXT_LEDGER_MISSING,
    SLIDE_COUNT_MISMATCH,
    BROWSER_RENDER_UNAVAILABLE,
    IMAGE_PPTX_UNAVAILABLE,
)

SLIDE_EMPTY = IssueKind("SLIDE_EMPTY", WARNING, "a slide has no text", "check that the slide exported")
SLIDE_TITLE_MISSING = IssueKind("SLIDE_TITLE_MISSING", WARNING, "a slide has no title", "give every slide a title")
TOO_MANY_SHAPES = IssueKind("TOO_MANY_SHAPES", WARNING, "a slide has more than 40 shapes", "simplify the slide")
DEFAULT_FONT_REMAINS = IssueKind("DEFAULT_FONT_REMAINS", WARNING, "text still uses Aptos or Calibri", "set the deck's own font")
THEME_FONT_INHERITED = IssueKind("THEME_FONT_INHERITED", WARNING, "text runs inherit the theme font", "set the font on every run")
OVERLAY_WITHOUT_BACKGROUND = IssueKind("OVERLAY_WITHOUT_BACKGROUND", WARNING, "editable overlays have no hybrid background image", "add the background image or remove the overlays")
OVERLAY_OUT_OF_BOUNDS = IssueKind("OVERLAY_OUT_OF_BOUNDS", WARNING, "an editable overlay extends past the slide", "move the overlay inside the slide")

VALIDATE_ISSUE_KINDS = (SLIDE_EMPTY, SLIDE_TITLE_MISSING, TOO_MANY_SHAPES, DEFAULT_FONT_REMAINS, THEME_FONT_INHERITED, OVERLAY_WITHOUT_BACKGROUND, OVERLAY_OUT_OF_BOUNDS)

REVIEW_REPORT_MISSING = IssueKind("REVIEW_REPORT_MISSING", ERROR, "slide-review.json is absent from the review directory", "run office deck build first")
REVIEW_DECISION_MISSING = IssueKind("REVIEW_DECISION_MISSING", WARNING, "review-decision.json is absent", "attach the usable deck with the review report notes if the requested file exists")
CONTACT_SHEETS_NOT_INSPECTED = IssueKind("CONTACT_SHEETS_NOT_INSPECTED", WARNING, "inspectedEvidence omits contact sheets", "open every contact sheet and list it in inspectedEvidence")
WARNINGS_NOT_ADDRESSED = IssueKind("WARNINGS_NOT_ADDRESSED", WARNING, "review warnings are not addressed in the decision", "list them in acceptedWarnings, remainingNotes, or issues, or rebuild a clean deck")
DECISION_SUMMARY_MISSING = IssueKind("DECISION_SUMMARY_MISSING", WARNING, "the review decision has no summary", "write a one-line summary")
DECISION_FIELD_NOT_LIST = IssueKind("DECISION_FIELD_NOT_LIST", WARNING, "a review decision field is not a list", "write the field as a JSON array")

ACCEPT_ISSUE_KINDS = (REVIEW_REPORT_MISSING, REVIEW_DECISION_MISSING, CONTACT_SHEETS_NOT_INSPECTED, WARNINGS_NOT_ADDRESSED, DECISION_SUMMARY_MISSING, DECISION_FIELD_NOT_LIST)

IMAGE_SEARCH_FAILED = IssueKind("IMAGE_SEARCH_FAILED", ERROR, "the image search could not be reached", "skip imagery or try a simpler English query")
NO_IMAGE_FOUND = IssueKind("NO_IMAGE_FOUND", ERROR, "no usable public-domain image matched", "try a simpler English query or skip imagery")

IMAGE_ISSUE_KINDS = (IMAGE_SEARCH_FAILED, NO_IMAGE_FOUND)

GUIDE_INPUTS = ()
GUIDE_ISSUES = (
    ("deck build", BUILD_ISSUE_KINDS + REVIEW_ISSUE_KINDS),
    ("deck validate", VALIDATE_ISSUE_KINDS),
    ("deck restore", (NO_SLIDE_SECTIONS,)),
    ("deck accept", ACCEPT_ISSUE_KINDS),
    ("deck image", IMAGE_ISSUE_KINDS),
)
