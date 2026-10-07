from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import threading
import unittest

from host_fixture import FakeHost, HostAnswer

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from PIL import Image  # noqa: E402

from delivery import visual_review  # noqa: E402
from delivery.office_deck import OfficeDeck, RebuildError  # noqa: E402
from delivery.review_images import MAXIMUM_IMAGE_BYTES, SHEET_GAP, contact_sheet, fit_image, sheet_columns  # noqa: E402
from delivery.review_manifest import Manifest, ManifestError, Question, Slide, parse_manifest  # noqa: E402
from delivery.visual_review import MAXIMUM_REFUSAL_CHARACTERS, ReviewLoop, rejection_reason, run_review, visible_text  # noqa: E402

CLEAN_OPTION = "none"
REPETITIVE_OPTION = "repetitive_layout"
INCONSISTENT_OPTION = "inconsistent_style"
EVERYTHING_ALLOWED = math.inf


def sample_options() -> dict:
    return {CLEAN_OPTION: "clean", "crowded": "packed densely", "unreadable_chart": "chart squashed"}


def deck_question() -> Question:
    return Question("Which pattern does this slide show across the deck?", {CLEAN_OPTION: "no pattern", REPETITIVE_OPTION: "same composition as another slide", INCONSISTENT_OPTION: "styled unlike the rest"}, CLEAN_OPTION)


def sample_manifest(rounds: int, *sections: str, deck: Question | None = None, pattern_thresholds: dict | None = None) -> Manifest:
    slides = tuple(Slide(number=index + 1, section=section, state={"theme": "corporate"}) for index, section in enumerate(sections))
    return Manifest(Question("Which defect?", sample_options(), CLEAN_OPTION), deck or Question(), 0.3, pattern_thresholds or {}, rounds, "Repair the slide.", "", slides)


def section(body: str) -> str:
    return '<section data-layout="split">' + body + "</section>"


def appended_body(original: str, addition: str) -> str:
    return original.replace("</section>", addition + "</section>", 1)


def flat_png(width: int, height: int, fill) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), fill).save(buffer, format="PNG")
    return buffer.getvalue()


def noisy_png(width: int, height: int) -> bytes:
    generator = random.Random(1)
    buffer = io.BytesIO()
    Image.frombytes("RGB", (width, height), bytes(generator.getrandbits(8) for _ in range(width * height * 3))).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeDeck:
    def __init__(self, manifest: Manifest, rendered: bool = False, large: bool = False):
        self.lock = threading.Lock()
        self.current = manifest
        self.renders: dict[str, bytes] = {}
        self.versions = 0
        self.rebuilds: list[dict] = []
        self.failure: str | None = None
        self.refuses = None
        self.rendered = rendered
        self.large = large
        self.render()

    def render(self) -> None:
        self.versions += 1
        slides = []
        for slide in self.current.slides:
            image = slide.section + "#" + chr(ord("a") + self.versions)
            self.renders[image] = slide.section.encode("utf-8")
            slides.append(Slide(slide.number, image, slide.state, slide.section, slide.source, slide.recompose, slide.measured))
        self.current = Manifest(self.current.question, self.current.deck, self.current.threshold, self.current.pattern_thresholds, self.current.rounds, self.current.fixer_instructions, self.current.source, tuple(slides))

    def manifest(self) -> Manifest:
        return self.current

    def image(self, path: str) -> bytes:
        if self.large:
            return noisy_png(1600, 900)
        if self.rendered:
            return flat_png(160, 90, (120, 120, 120))
        with self.lock:
            return self.renders[path]

    def rebuild(self, replacements: dict[int, str]) -> Manifest:
        with self.lock:
            if self.failure is not None:
                raise RebuildError(self.failure)
            for replacement in replacements.values():
                if self.refuses is not None and self.refuses(replacement):
                    raise RebuildError("the build refused " + replacement)
            self.rebuilds.append(dict(replacements))
            slides = tuple(Slide(slide.number, slide.image, slide.state, replacements.get(slide.number, slide.section), slide.source, slide.recompose, slide.measured) for slide in self.current.slides)
            self.current = Manifest(self.current.question, self.current.deck, self.current.threshold, self.current.pattern_thresholds, self.current.rounds, self.current.fixer_instructions, self.current.source, slides)
            self.render()
            return self.current

    def section_of(self, number: int) -> str:
        return self.current.slides[number - 1].section


def distribution_by_content(content: str) -> dict:
    if "BAD" in content:
        return {CLEAN_OPTION: 0.6, "unreadable_chart": 0.35, "crowded": 0.05}
    return {CLEAN_OPTION: 0.95, "crowded": 0.05}


def near_miss_distribution(content: str) -> dict:
    return {CLEAN_OPTION: 0.65, "unreadable_chart": 0.27, "crowded": 0.08}


def image_text(body: dict) -> str:
    return base64.b64decode(body["images"][0]["data"]).decode("utf-8", errors="replace")


def slide_decider(answer, deck_probabilities=None, deck_failure: str = ""):
    def decide(body: dict) -> dict:
        if "visual_defect" in body["questions"]:
            probabilities = answer(image_text(body))
            return {"answers": {"visual_defect": {"type": "choice", "probabilities": probabilities}}, "usage": {"costUSD": 0.5}}
        if deck_failure:
            raise HostAnswer(502, deck_failure)
        answers = {name: {"type": "choice", "probabilities": deck_probabilities(int(name.removeprefix("slide_")))} for name in body["questions"]}
        return {"answers": answers, "usage": {"costUSD": 0.25}}
    return decide


def clean_slides(content: str) -> dict:
    return {CLEAN_OPTION: 0.95}


def fixer(rewrite):
    def generate(body: dict) -> dict:
        repair = rewrite(json.loads(body["prompt"])["section"])
        return {"answer": repair, "usage": {"costUSD": 0.0}}
    return generate


def repetition_of(deck: FakeDeck):
    def probabilities(number: int) -> dict:
        if "SAME" in deck.section_of(number):
            return {CLEAN_OPTION: 0.4, REPETITIVE_OPTION: 0.6}
        return {CLEAN_OPTION: 0.97, REPETITIVE_OPTION: 0.03}
    return probabilities


def repair(text: str, change: str) -> dict:
    return {"section": text, "change": change}


def varying_fixer():
    return fixer(lambda original: repair(original.replace("SAME", "varied", 1), "recomposed"))


def run_loop(deck: FakeDeck, decide, generate=None, deadline: float = EVERYTHING_ALLOWED) -> tuple[dict, FakeHost, ReviewLoop]:
    with FakeHost(decide=decide, generate=generate or fixer(lambda original: repair(original, "nothing"))) as host:
        loop = ReviewLoop(deck)
        loop.run(deadline)
    return loop.report(), host, loop


def payload_of(body: dict) -> dict:
    return json.loads(body["prompt"])


class SlideReviewTest(unittest.TestCase):
    def test_flags_on_any_non_clean_option_at_threshold_even_when_clean_is_top(self):
        report, _, loop = run_loop(FakeDeck(sample_manifest(0, section("BAD"), section("fine"))), slide_decider(distribution_by_content))
        self.assertEqual([leftover["number"] for leftover in report["leftovers"]], [1])
        findings = report["slides"][0]["findings"]
        self.assertEqual([(finding["kind"], finding["meaning"]) for finding in findings], [("unreadable_chart", "chart squashed")])
        self.assertEqual(loop.cost, 1.0)
        self.assertEqual(loop.calls, 2)

    def test_a_pattern_threshold_flags_a_pattern_below_the_general_one(self):
        manifest = sample_manifest(0, section("near"), pattern_thresholds={"unreadable_chart": 0.2})
        report, _, _ = run_loop(FakeDeck(manifest), slide_decider(near_miss_distribution))
        self.assertEqual([(finding["kind"], finding["probability"]) for finding in report["slides"][0]["findings"]], [("unreadable_chart", 0.27)])

    def test_a_pattern_without_its_own_threshold_keeps_the_general_one(self):
        manifest = sample_manifest(0, section("near"), pattern_thresholds={"crowded": 0.05})
        report, _, _ = run_loop(FakeDeck(manifest), slide_decider(near_miss_distribution))
        self.assertNotIn("unreadable_chart", [finding["kind"] for finding in report["slides"][0]["findings"]])

    def test_a_measured_defect_flags_a_slide_the_reviewer_called_clean(self):
        manifest = sample_manifest(0, section("fine"))
        manifest = Manifest(manifest.question, manifest.deck, manifest.threshold, {}, 0, manifest.fixer_instructions, "", (Slide(1, section=section("fine"), state={"theme": "corporate"}, measured=({"code": "text-overflow", "message": "overflows"},)),))
        report, _, _ = run_loop(FakeDeck(manifest), slide_decider(distribution_by_content))
        self.assertEqual(report["leftovers"], [{"number": 1, "measured": ["text-overflow"]}])

    def test_the_request_carries_the_image_and_the_manifest_question_verbatim(self):
        _, host, _ = run_loop(FakeDeck(sample_manifest(0, section("fine"))), slide_decider(distribution_by_content))
        request = host.requests_to("decide")[0]
        self.assertEqual(request["questions"], {"visual_defect": {"type": "choice", "instructions": "Which defect?", "criteria": sample_options()}})
        self.assertEqual(len(request["images"]), 1)
        self.assertEqual(request["images"][0]["mediaType"], "image/png")
        self.assertEqual(image_text(request), section("fine"))
        self.assertEqual(request["state"]["theme"], "corporate")


class FixLoopTest(unittest.TestCase):
    def test_the_fixer_request_carries_the_guide_findings_and_image(self):
        deck = FakeDeck(sample_manifest(1, section("BAD")))
        _, host, _ = run_loop(deck, slide_decider(distribution_by_content), fixer(lambda original: repair(appended_body(original, "<p>x</p>"), "moved")))
        request = host.requests_to("generate")[0]
        self.assertEqual(request["system"], "Repair the slide.")
        self.assertEqual(len(request["images"]), 1)
        self.assertEqual(request["images"][0]["mediaType"], "image/png")
        payload = payload_of(request)
        self.assertEqual(payload["facts"]["theme"], "corporate")
        self.assertEqual((payload["reviewerFindings"][0]["kind"], payload["reviewerFindings"][0]["meaning"]), ("unreadable_chart", "chart squashed"))
        self.assertIs(request["schema"]["additionalProperties"], False)

    def test_only_fixed_slides_are_asked_again(self):
        deck = FakeDeck(sample_manifest(3, section("fine one"), section("BAD"), section("fine three")))
        report, host, _ = run_loop(deck, slide_decider(distribution_by_content), fixer(lambda original: repair(original.replace("BAD", "good", 1), "regrouped")))
        self.assertEqual((len(host.requests_to("decide")), len(host.requests_to("generate"))), (4, 1))
        self.assertEqual(report["leftovers"], [])
        self.assertEqual(report["fixed"], [{"number": 2, "change": "regrouped"}])
        self.assertEqual(report["roundsUsed"], 1)

    def test_a_fix_that_does_not_improve_is_restored_and_not_tried_again(self):
        deck = FakeDeck(sample_manifest(3, section("BAD")))
        report, host, _ = run_loop(deck, slide_decider(distribution_by_content), fixer(lambda original: repair(appended_body(original, "<p>same</p>"), "tried")))
        self.assertEqual((len(host.requests_to("generate")), len(deck.rebuilds)), (1, 2))
        self.assertEqual(deck.section_of(1), section("BAD"))
        self.assertEqual(report["givenUp"], [1])
        self.assertEqual([leftover["number"] for leftover in report["leftovers"]], [1])
        self.assertEqual((report["fixed"], report["textChanged"]), ([], []))

    def test_a_rewrite_that_turns_a_table_into_a_chart_is_rejected(self):
        deck = FakeDeck(sample_manifest(2, section("BAD<table><tr><td>1</td></tr></table>")))
        report, _, _ = run_loop(deck, slide_decider(distribution_by_content), fixer(lambda original: repair(section('BAD<div data-chart="bar"></div>'), "chart")))
        self.assertEqual((deck.rebuilds, report["fixed"]), ([], []))
        self.assertIn("tables, images and charts", report["slides"][0]["error"])

    def test_rejection_reason(self):
        table = section('<table></table><img src="a"><div data-chart="bar"></div>')
        cases = {
            "same parts reworded": (section('<img src="a"><div data-chart="bar"></div><table></table><p>x</p>'), True),
            "table dropped": (section('<img src="a"><div data-chart="bar"></div>'), False),
            "image added": (section('<table></table><img><img><div data-chart="bar"></div>'), False),
            "chart kind changed": (section('<table></table><img src="a"><div data-chart="line"></div>'), False),
            "two sections": (table + table, False),
            "text around the section": ("intro " + table, False),
            "unchanged": (table, False),
        }
        for name, (rewrite, accepted) in cases.items():
            with self.subTest(name):
                self.assertEqual(rejection_reason(table, rewrite) == "", accepted)

    def test_the_rounds_cap_stops_fixing(self):
        deck = FakeDeck(sample_manifest(2, section("start")))
        decide = slide_decider(lambda content: {CLEAN_OPTION: 0.5, "crowded": 0.9 - 0.1 * content.count("+")})
        report, host, _ = run_loop(deck, decide, fixer(lambda original: repair(appended_body(original, "+"), "step")))
        self.assertEqual(report["roundsUsed"], 2)
        self.assertEqual(len(host.requests_to("generate")), 2)
        self.assertEqual([leftover["number"] for leftover in report["leftovers"]], [1])
        self.assertEqual(report["givenUp"], [])

    def test_no_round_starts_after_the_deadline(self):
        deck = FakeDeck(sample_manifest(2, section("BAD")))
        report, host, _ = run_loop(deck, slide_decider(distribution_by_content), fixer(lambda original: repair(original.replace("BAD", "good"), "x")), deadline=-math.inf)
        self.assertEqual((report["roundsUsed"], host.requests_to("generate")), (0, []))
        self.assertEqual([leftover["number"] for leftover in report["leftovers"]], [1])

    def test_a_text_change_is_reported_only_when_visible_words_differ(self):
        deck = FakeDeck(sample_manifest(1, section('<p data-x="BAD">one</p>'), section('<p data-x="BAD">two</p>')))

        def rewrite(original: str) -> dict:
            if "one" in original:
                return repair(section('<p data-x="ok">one</p><aside class="notes">new note</aside>'), "notes only")
            return repair(section('<p data-x="ok">three</p>'), "reworded")

        report, _, _ = run_loop(deck, slide_decider(distribution_by_content), fixer(rewrite))
        self.assertEqual(report["textChanged"], [2])
        self.assertEqual(len(report["fixed"]), 2)

    def test_visible_text_ignores_tags_attributes_and_notes(self):
        first = visible_text(section('<h2 class="a">Sales   up</h2><aside class="notes">hidden</aside><p>10&amp;20</p>'))
        second = visible_text(section('<p style="x">Sales up</p><h2>10&20</h2><aside class="notes extra">other</aside>'))
        self.assertEqual(first, "Sales up 10&20")
        self.assertEqual(first, second)

    def test_a_rewrite_the_build_refuses_is_retried_with_the_refusal_in_front_of_the_fixer(self):
        deck = FakeDeck(sample_manifest(2, section("BAD")))
        deck.failure = "office failed on slide 1"
        report, host, _ = run_loop(deck, slide_decider(distribution_by_content), fixer(lambda original: repair(appended_body(original, "<p>x</p>"), "x")))
        requests = host.requests_to("generate")
        self.assertEqual(len(requests), 2)
        self.assertEqual([leftover["number"] for leftover in report["leftovers"]], [1])
        self.assertEqual(report["givenUp"], [])
        self.assertIn("office failed on slide 1", report["slides"][0]["error"])
        self.assertNotIn("refusedLastTime", payload_of(requests[0]))
        self.assertIn("office failed on slide 1", payload_of(requests[1])["refusedLastTime"])

    def test_a_refusal_is_cut_to_a_length_the_fixer_can_read(self):
        deck = FakeDeck(sample_manifest(2, section("BAD")))
        deck.failure = "x" * 5000
        _, host, _ = run_loop(deck, slide_decider(distribution_by_content), fixer(lambda original: repair(appended_body(original, "<p>x</p>"), "x")))
        self.assertLessEqual(len(payload_of(host.requests_to("generate")[1])["refusedLastTime"]), MAXIMUM_REFUSAL_CHARACTERS)

    def test_one_refused_rewrite_does_not_discard_the_others_the_build_accepts(self):
        deck = FakeDeck(sample_manifest(1, section("BAD one"), section("BAD two"), section("BAD three")))
        deck.refuses = lambda replacement: "two" in replacement
        report, _, _ = run_loop(deck, slide_decider(distribution_by_content), fixer(lambda original: repair(original.replace("BAD", "good", 1), "regrouped")))
        self.assertEqual([fixed["number"] for fixed in report["fixed"]], [1, 3])
        self.assertEqual(report["givenUp"], [])
        self.assertEqual([leftover["number"] for leftover in report["leftovers"]], [2])
        self.assertIn("the build refused", report["slides"][1]["error"])
        self.assertEqual(deck.section_of(2), section("BAD two"))

    def test_a_page_the_claim_check_emptied_is_recomposed_once_even_when_the_reviewer_called_it_clean(self):
        manifest = sample_manifest(3, section("fine one"), section("fine two"))
        slides = (manifest.slides[0], Slide(2, section=section("fine two"), state={"theme": "corporate"}, recompose=True))
        manifest = Manifest(manifest.question, manifest.deck, manifest.threshold, {}, 3, manifest.fixer_instructions, "", slides)
        deck = FakeDeck(manifest)
        report, host, _ = run_loop(deck, slide_decider(distribution_by_content), fixer(lambda original: repair(original.replace("fine two", "fine two, recomposed", 1), "recomposed")))
        self.assertEqual((len(host.requests_to("generate")), len(deck.rebuilds)), (1, 1))
        self.assertEqual(report["fixed"], [{"number": 2, "change": "recomposed"}])
        self.assertEqual(report["givenUp"], [])
        payload = payload_of(host.requests_to("generate")[0])
        self.assertIs(payload["recompose"], True)
        self.assertEqual(payload["facts"]["theme"], "corporate")


    def test_a_remake_reviews_and_recomposes_only_the_pages_the_claim_check_emptied_in_one_round(self):
        manifest = sample_manifest(3, section("BAD one"), section("fine two"), deck=deck_question())
        slides = (manifest.slides[0], Slide(2, section=section("fine two"), state={"theme": "corporate"}, recompose=True))
        deck = FakeDeck(Manifest(manifest.question, manifest.deck, manifest.threshold, {}, 3, manifest.fixer_instructions, "", slides))
        with FakeHost(decide=slide_decider(distribution_by_content, repetition_of(deck)), generate=fixer(lambda original: repair(original.replace("fine two", "BAD two", 1), "recomposed"))) as host:
            loop = ReviewLoop(deck, is_recompose_only=True)
            loop.run(EVERYTHING_ALLOWED)
        reviewed = [image_text(body) for body in host.requests_to("decide") if "visual_defect" in body["questions"]]
        self.assertTrue(all("two" in text for text in reviewed), reviewed)
        self.assertFalse(any("visual_defect" not in body["questions"] for body in host.requests_to("decide")))
        self.assertEqual(len(host.requests_to("generate")), 1)


    def test_a_fix_that_clears_a_measured_defect_is_kept_when_the_reviewer_sees_it_no_worse(self):
        before = visual_review.Assessment(probabilities={"wasted_space": 0.6}, findings=[{"kind": "wasted_space", "probability": 0.6}], measured=({"code": "EMPTY_LOWER_BAND"},))
        same = visual_review.Assessment(probabilities={"wasted_space": 0.6}, findings=[{"kind": "wasted_space", "probability": 0.6}])
        worse = visual_review.Assessment(probabilities={"wasted_space": 0.7}, findings=[{"kind": "wasted_space", "probability": 0.7}])
        self.assertTrue(visual_review.is_improved(before, same))
        self.assertFalse(visual_review.is_improved(before, worse))


class DeckReviewTest(unittest.TestCase):
    def deck(self, rounds: int, *sections: str, large: bool = False) -> FakeDeck:
        return FakeDeck(sample_manifest(rounds, *sections, deck=deck_question()), rendered=True, large=large)

    def test_a_deck_question_is_asked_once_with_one_sheet_and_one_question_per_slide(self):
        deck = self.deck(0, section("a"), section("b"), section("c"))
        report, host, loop = run_loop(deck, slide_decider(clean_slides, repetition_of(deck)))
        deck_requests = [body for body in host.requests_to("decide") if "visual_defect" not in body["questions"]]
        self.assertEqual((len(deck_requests), len(host.requests_to("decide")) - len(deck_requests)), (1, 3))
        request = deck_requests[0]
        self.assertEqual((len(request["images"]), len(request["questions"])), (1, 3))
        self.assertEqual(request["questions"]["slide_2"], {"type": "choice", "instructions": deck_question().instructions + " Judge slide 2.", "criteria": deck_question().options})
        self.assertEqual(report["leftovers"], [])

    def test_a_slide_the_deck_call_flags_is_recomposed_with_the_sheet_beside_it(self):
        deck = self.deck(1, section("one"), section("SAME two"), section("three"))
        report, host, _ = run_loop(deck, slide_decider(clean_slides, repetition_of(deck)), varying_fixer())
        requests = host.requests_to("generate")
        self.assertEqual(len(requests), 1)
        self.assertEqual(len(requests[0]["images"]), 2)
        findings = payload_of(requests[0])["reviewerFindings"]
        self.assertEqual([(finding["kind"], finding["meaning"]) for finding in findings], [(REPETITIVE_OPTION, "same composition as another slide")])
        deck_requests = [body for body in host.requests_to("decide") if "visual_defect" not in body["questions"]]
        self.assertEqual(len(deck_requests), 2)
        self.assertEqual(report["leftovers"], [])
        self.assertEqual([fixed["number"] for fixed in report["fixed"]], [2])
        self.assertEqual([(flagged["number"], flagged["findings"][0]["kind"]) for flagged in report["deckFlagged"]], [(2, REPETITIVE_OPTION)])

    def test_a_slide_with_no_sheet_beside_it_is_fixed_without_one(self):
        deck = self.deck(1, section("BAD"))
        decide = slide_decider(lambda content: {CLEAN_OPTION: 0.5, "crowded": 0.5}, repetition_of(deck))
        _, host, _ = run_loop(deck, decide, fixer(lambda original: repair(original.replace("BAD", "good", 1), "regrouped")))
        self.assertEqual(len(host.requests_to("generate")[0]["images"]), 1)

    def test_a_deck_flag_with_no_rounds_is_reported_and_nothing_is_rewritten(self):
        deck = self.deck(0, section("SAME one"), section("two"))
        report, host, _ = run_loop(deck, slide_decider(clean_slides, repetition_of(deck)), varying_fixer())
        self.assertEqual((host.requests_to("generate"), deck.rebuilds), ([], []))
        self.assertEqual([leftover["number"] for leftover in report["leftovers"]], [1])

    def test_a_recomposition_the_deck_call_still_flags_is_restored(self):
        deck = self.deck(1, section("SAME one"), section("two"))
        report, _, _ = run_loop(deck, slide_decider(clean_slides, repetition_of(deck)), fixer(lambda original: repair(appended_body(original, "<p>shuffled</p>"), "shuffled")))
        self.assertEqual(deck.section_of(1), section("SAME one"))
        self.assertEqual(report["givenUp"], [1])
        self.assertEqual([leftover["number"] for leftover in report["leftovers"]], [1])

    def test_a_deck_call_that_fails_is_reported_and_the_run_still_finishes(self):
        deck = self.deck(1, section("a"))
        report, _, _ = run_loop(deck, slide_decider(clean_slides, repetition_of(deck), deck_failure="decisions endpoint answered 500"))
        self.assertIn("500", report["deckError"])
        self.assertEqual(report["leftovers"], [])

    def test_a_manifest_without_a_deck_question_never_builds_a_sheet(self):
        deck = FakeDeck(sample_manifest(1, section("a")), rendered=True)
        _, host, _ = run_loop(deck, slide_decider(clean_slides, repetition_of(deck)))
        self.assertTrue(all("visual_defect" in body["questions"] for body in host.requests_to("decide")))

    def test_a_deck_call_still_runs_when_every_rewrite_was_refused(self):
        deck = self.deck(1, section("BAD"))
        deck.refuses = lambda replacement: True
        decide = slide_decider(lambda content: {CLEAN_OPTION: 0.5, "crowded": 0.5}, repetition_of(deck))
        _, host, _ = run_loop(deck, decide, fixer(lambda original: repair(appended_body(original, "<p>x</p>"), "x")))
        self.assertEqual(len([body for body in host.requests_to("decide") if "visual_defect" not in body["questions"]]), 1)

    def test_every_render_is_shrunk_to_fit_before_it_is_sent(self):
        deck = self.deck(0, section("a"), section("b"), large=True)
        report, host, _ = run_loop(deck, slide_decider(clean_slides, repetition_of(deck)))
        for body in host.requests_to("decide"):
            for image in body.get("images") or ():
                self.assertLessEqual(len(base64.b64decode(image["data"])), MAXIMUM_IMAGE_BYTES)
        self.assertEqual([slide["error"] for slide in report["slides"]], ["", ""])

    def test_the_deck_call_shares_the_manifests_fix_rounds_with_the_slide_review(self):
        deck = self.deck(2, section("SAME start"))
        reviews = []

        def slide_answer(content: str) -> dict:
            reviews.append(content)
            return {CLEAN_OPTION: 0.5, "crowded": 1 - 0.1 * len(reviews)}

        report, host, _ = run_loop(deck, slide_decider(slide_answer, repetition_of(deck)), fixer(lambda original: repair(appended_body(original, "+"), "step")))
        requests = host.requests_to("generate")
        self.assertEqual((report["roundsUsed"], len(requests)), (2, 2))
        self.assertIn(REPETITIVE_OPTION, [finding["kind"] for finding in payload_of(requests[0])["reviewerFindings"]])


class ManifestTest(unittest.TestCase):
    VALID = '{"question":{"instructions":"q","options":{"none":"clean","crowded":"c"},"cleanOption":"none"},"threshold":0.3,"rounds":3,"fixer":{"instructions":"f"},"source":"/a","slides":[{"number":1,"image":"/a.png","state":{"theme":{}},"section":"<section></section>","measured":[]}]}'

    def test_a_manifest_is_validated(self):
        manifest = parse_manifest(self.VALID)
        self.assertEqual((manifest.slides[0].number, manifest.rounds), (1, 3))
        invalid = {
            "missing clean option": self.VALID.replace('"cleanOption":"none"', '"cleanOption":"other"', 1),
            "threshold of one": self.VALID.replace('"threshold":0.3', '"threshold":1', 1),
            "threshold of zero": self.VALID.replace('"threshold":0.3', '"threshold":0', 1),
            "negative rounds": self.VALID.replace('"rounds":3', '"rounds":-1', 1),
            "not json": "{",
        }
        for name, content in invalid.items():
            with self.subTest(name), self.assertRaises(ManifestError):
                parse_manifest(content)

    def test_a_pattern_threshold_naming_no_option_is_refused(self):
        with self.assertRaises(ManifestError):
            parse_manifest(self.VALID.replace('"rounds":3', '"rounds":3,"patternThresholds":{"not_an_option":0.2}'))

    def with_deck(self, deck: dict, extra: str = "") -> str:
        return self.VALID.replace('"rounds":3', '"rounds":3,"deck":' + json.dumps(deck) + extra)

    def test_a_deck_question_is_validated(self):
        deck = {"instructions": "d", "options": {"none": "no", REPETITIVE_OPTION: "same"}, "cleanOption": "none"}
        self.assertTrue(parse_manifest(self.with_deck(deck)).asks_about_the_deck())
        self.assertTrue(parse_manifest(self.with_deck(deck, ',"patternThresholds":{"repetitive_layout":0.2}')).pattern_thresholds)
        for name, changed in {"clean option missing": deck | {"cleanOption": "nothing"}, "option shared with the slide question": deck | {"options": deck["options"] | {"crowded": "also"}}}.items():
            with self.subTest(name), self.assertRaises(ManifestError):
                parse_manifest(self.with_deck(changed))

    def test_page_source_names_the_file_a_slide_is_written_from(self):
        manifest = sample_manifest(1, section("one"), section("two"))
        manifest = Manifest(manifest.question, manifest.deck, 0.3, {}, 1, "", "", (manifest.slides[0], Slide(2, source="/deck/pages/02.html")))
        self.assertEqual((manifest.page_source(1), manifest.page_source(2), manifest.page_source(3)), ("", "/deck/pages/02.html", ""))


class ImageTest(unittest.TestCase):
    def test_an_image_within_the_budget_is_sent_untouched(self):
        original = flat_png(1600, 900, (255, 255, 255))
        fitted = fit_image(original)
        self.assertEqual((fitted.data, fitted.media_type), (original, "image/png"))

    def test_an_image_over_the_budget_is_downscaled_until_it_fits(self):
        original = noisy_png(1600, 900)
        self.assertGreater(len(original), MAXIMUM_IMAGE_BYTES)
        fitted = fit_image(original)
        self.assertLessEqual(len(fitted.data), MAXIMUM_IMAGE_BYTES)
        self.assertEqual(fitted.media_type, "image/jpeg")
        with Image.open(io.BytesIO(fitted.data)) as picture:
            self.assertLess(picture.width, 1600)
            self.assertLessEqual(abs(picture.width * 9 - picture.height * 16), 16)

    def test_bytes_that_are_not_an_image_are_refused_when_too_large_to_send_as_they_are(self):
        with self.assertRaises(ValueError):
            fit_image(b"x" * (MAXIMUM_IMAGE_BYTES + 1))

    def test_a_contact_sheet_lays_the_renders_out_in_reading_order_each_under_its_number(self):
        fills = [(200, 30, 30), (30, 200, 30), (30, 30, 200), (200, 200, 30), (30, 200, 200), (200, 30, 200)]
        sheet = contact_sheet([flat_png(1600, 900, fill) for fill in fills])
        with Image.open(io.BytesIO(sheet.data)) as opened:
            picture = opened.convert("RGB")
        columns, rows = 3, 2
        self.assertEqual(sheet_columns(len(fills)), columns)
        tile_width = (picture.width - (columns + 1) * SHEET_GAP) // columns
        tile_height = tile_width * 9 // 16
        self.assertEqual(picture.height, rows * tile_height + (rows + 1) * SHEET_GAP)
        for index, fill in enumerate(fills):
            left = SHEET_GAP + (index % columns) * (tile_width + SHEET_GAP)
            top = SHEET_GAP + (index // columns) * (tile_height + SHEET_GAP)
            centre = picture.getpixel((left + tile_width // 2, top + tile_height // 2))
            self.assertTrue(all(abs(got - wanted) <= 12 for got, wanted in zip(centre, fill)), (index, centre, fill))
            self.assertTrue(all(channel <= 40 for channel in picture.getpixel((left + 1, top + 1))))

    def test_a_contact_sheet_stays_within_the_image_budget(self):
        sheet = contact_sheet([noisy_png(640, 360) for _ in range(12)])
        self.assertLessEqual(len(sheet.data), MAXIMUM_IMAGE_BYTES)

    def test_a_contact_sheet_of_nothing_is_refused(self):
        with self.assertRaises(ValueError):
            contact_sheet([])


FLAWED_SECTION = '<section data-layout="split"><p>BAD crowded 99%</p></section>'
REPAIRED_SECTION = '<section data-layout="split"><p>GOOD crowded 99%</p></section>'
COVER_SECTION = '<section data-layout="cover"><h1>Cover</h1></section>'

STAND_IN_OFFICE = '''import pathlib, shutil, sys
directory = pathlib.Path(sys.argv[3])
with open(directory / "office-calls.txt", "a", encoding="utf-8") as record:
    record.write(" ".join(sys.argv[1:]) + "\\n")
shutil.copyfile(directory / "rebuilt-manifest.json", directory / "manifest.json")
shutil.copyfile(directory / "rebuilt-snapshot.json", sys.argv[2] + ".source.json")
raise SystemExit(int((directory / "exit-code").read_text()))
'''


class OfficeDeckFixture:
    def __init__(self, exit_code: int = 0):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.directory = root / "artifacts" / "deck"
        self.document = root / "documents" / "deck.pptx"
        self.document.parent.mkdir(parents=True)
        self.document.write_bytes(b"deck-bytes")
        self.page(1).parent.mkdir(parents=True)
        self.page(1).write_text(COVER_SECTION + "\n", encoding="utf-8")
        self.page(2).write_text(FLAWED_SECTION + "\n", encoding="utf-8")
        for name, content in (("render-1.png", "COVER"), ("render-2.png", "BAD"), ("render-3.png", "GOOD")):
            (self.directory / name).write_text(content, encoding="utf-8")
        (self.directory / "manifest.json").write_text(self.manifest_json([COVER_SECTION, FLAWED_SECTION], ["render-1.png", "render-2.png"]), encoding="utf-8")
        (self.directory / "rebuilt-manifest.json").write_text(self.manifest_json([COVER_SECTION, REPAIRED_SECTION], ["render-1.png", "render-3.png"]), encoding="utf-8")
        (self.directory / "rebuilt-snapshot.json").write_text(json.dumps(self.snapshot()), encoding="utf-8")
        (self.directory / "exit-code").write_text(str(exit_code), encoding="utf-8")
        self.entry = root / "office"
        self.entry.write_text(STAND_IN_OFFICE, encoding="utf-8")

    def page(self, number: int) -> Path:
        return self.directory / "pages" / f"{number:02d}.html"

    def manifest_json(self, sections: list[str], renders: list[str]) -> str:
        slides = [{"number": index + 1, "image": str(self.directory / renders[index]), "state": {"number": index + 1}, "section": text, "source": str(self.page(index + 1)), "measured": []} for index, text in enumerate(sections)]
        return json.dumps({"question": {"instructions": "Which defect?", "options": {"none": "clean", "crowded": "packed densely"}, "cleanOption": "none"},
                           "threshold": 0.3, "rounds": 2, "fixer": {"instructions": "Repair the slide."}, "source": str(self.directory), "slides": slides})

    def snapshot(self) -> dict:
        return {"command": "office create", "arguments": [str(self.document), str(self.directory)], "deck": str(self.directory), "visualReview": str(self.directory / "manifest.json")}

    def calls(self) -> list[str]:
        path = self.directory / "office-calls.txt"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def review(self, generate=None) -> tuple[visual_review.VisualReview, FakeHost]:
        decide = slide_decider(lambda content: {"none": 0.6, "crowded": 0.4} if "BAD" in content else {"none": 0.95, "crowded": 0.05})
        generate = generate or fixer(lambda original: repair(original.replace("BAD", "GOOD"), "spread the text over two columns"))
        with FakeHost(decide=decide, generate=generate) as host:
            review = run_review(OfficeDeck(self.document, self.snapshot(), office_entry=self.entry), self.document.name, EVERYTHING_ALLOWED)
        return review, host


class OfficeDeckTest(unittest.TestCase):
    def fixture(self, exit_code: int = 0) -> OfficeDeckFixture:
        fixture = OfficeDeckFixture(exit_code)
        self.addCleanup(fixture.temporary.cleanup)
        return fixture

    def test_a_flagged_slide_is_rewritten_in_its_page_file_and_the_deck_rebuilt_with_its_recorded_command(self):
        fixture = self.fixture()
        review, _ = fixture.review()
        self.assertEqual(fixture.page(2).read_text(encoding="utf-8"), REPAIRED_SECTION + "\n")
        self.assertEqual(fixture.page(1).read_text(encoding="utf-8"), COVER_SECTION + "\n")
        self.assertEqual(fixture.calls(), [f"create {fixture.document} {fixture.directory}"])
        document = review.to_json()
        self.assertEqual((document["outcome"], document["roundsUsed"]), ("fixed", 1))
        self.assertEqual(document["fixed"], [{"number": 2, "change": "spread the text over two columns"}])
        self.assertEqual(review.calls, 4)

    def test_a_clean_deck_is_delivered_without_a_fix_or_a_rebuild(self):
        fixture = self.fixture()
        (fixture.directory / "render-2.png").write_text("FINE", encoding="utf-8")
        review, host = fixture.review()
        self.assertEqual((fixture.calls(), host.requests_to("generate")), ([], []))
        self.assertEqual(len(host.requests_to("decide")), 2)
        self.assertEqual(review.outcome, "clean")

    def test_a_refused_rebuild_keeps_the_slide_flagged_and_restores_its_page(self):
        fixture = self.fixture(exit_code=1)
        review, _ = fixture.review()
        self.assertEqual(fixture.page(2).read_text(encoding="utf-8"), FLAWED_SECTION + "\n")
        self.assertEqual(review.outcome, "leftovers")

    def test_a_slide_the_fixer_could_not_repair_is_a_leftover(self):
        fixture = self.fixture()

        def unavailable(body: dict) -> dict:
            raise HostAnswer(502, "language model unavailable")

        review, _ = fixture.review(generate=unavailable)
        self.assertEqual(review.outcome, "leftovers")
        self.assertEqual(review.leftovers, [{"number": 2, "findings": ["crowded"]}])

    def test_a_host_without_an_image_model_reviews_nothing(self):
        fixture = self.fixture()
        with FakeHost(generate=fixer(lambda original: repair(original, "x"))):
            review = run_review(OfficeDeck(fixture.document, fixture.snapshot(), office_entry=fixture.entry), fixture.document.name, EVERYTHING_ALLOWED)
        self.assertEqual(review.outcome, "unavailable")
        self.assertEqual(fixture.calls(), [])


if __name__ == "__main__":
    unittest.main()
