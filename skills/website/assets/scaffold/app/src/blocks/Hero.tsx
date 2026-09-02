import { buttonVariants } from "../components/ui/button";
import type { Block } from "../site-content";
import { splitParagraphs } from "./textParagraphs";
import { BackdropCanvas } from "./BackdropCanvas";

const knownBackdrops = new Set(["mesh", "aurora", "grain", "grid", "dots"]);

function canvasKindFor(backdrop: string | undefined): "mesh" | "aurora" | "grain" | undefined {
	if (backdrop === "mesh" || backdrop === "aurora" || backdrop === "grain") return backdrop;
	return undefined;
}

type HeroProps = {
	block: Block;
	anchorID: string;
};

export function Hero({ block, anchorID }: HeroProps) {
	const heroText = (
		<div className="flex flex-col justify-center">
			{block.title ? (
				<h1 className="max-w-3xl text-[clamp(2.75rem,6vw,4.25rem)] font-bold leading-[1.04] tracking-tight">
					{block.title}
				</h1>
			) : null}
			{splitParagraphs(block.body).map((paragraph, paragraphIndex) => (
				<p key={paragraphIndex} className="hero-muted mt-7 max-w-2xl text-xl leading-relaxed">
					{paragraph}
				</p>
			))}
			{block.actionLabel ? (
				<div className="mt-10">
					<a href={block.actionHref ?? "#"} className={buttonVariants({ size: "lg", className: "hero-cta px-8 py-6 text-base" })}>
						{block.actionLabel}
					</a>
				</div>
			) : null}
		</div>
	);
	const backdropClass = knownBackdrops.has(block.backdrop ?? "") ? ` backdrop-${block.backdrop}` : "";
	return (
		<section id={anchorID} className={"hero-band full-bleed px-6" + backdropClass}>
			{canvasKindFor(block.backdrop) ? <BackdropCanvas kind={canvasKindFor(block.backdrop) ?? "mesh"} /> : null}
			<div className="mx-auto max-w-4xl py-24">
				{block.image ? (
					<div className="grid min-h-[52vh] items-center gap-12 md:grid-cols-[1.1fr_0.9fr]">
						{heroText}
						<img
							src={block.image}
							alt={block.imageAlt ?? ""}
							className="h-full max-h-[26rem] w-full rounded-[calc(var(--radius-lg)*1.5)] object-cover"
						/>
					</div>
				) : (
					<div className="flex min-h-[52vh] flex-col justify-center">{heroText}</div>
				)}
			</div>
		</section>
	);
}
