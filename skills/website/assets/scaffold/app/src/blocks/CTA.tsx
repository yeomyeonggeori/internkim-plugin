import { buttonVariants } from "../components/ui/button";
import type { Block } from "../site-content";

type CTAProps = {
	block: Block;
	anchorID: string;
};

const knownBackdrops = new Set(["mesh", "aurora", "grain", "grid", "dots"]);

export function CTA({ block, anchorID }: CTAProps) {
	const backdropClass = knownBackdrops.has(block.backdrop ?? "") ? ` backdrop-${block.backdrop}` : "";
	return (
		<section id={anchorID} className="py-16">
			<div className={"rounded-[calc(var(--radius-lg)*1.5)] bg-primary px-10 py-16 text-center text-primary-foreground sm:px-16" + backdropClass}>
				{block.title ? <h2 className="mx-auto max-w-2xl text-[clamp(1.75rem,3.5vw,2.5rem)] font-bold leading-tight tracking-tight">{block.title}</h2> : null}
				{block.body ? <p className="mx-auto mt-4 max-w-xl text-lg leading-relaxed opacity-85">{block.body}</p> : null}
				{block.actionLabel ? (
					<a
						href={block.actionHref ?? "#"}
						className={buttonVariants({ variant: "secondary", size: "lg", className: "mt-8 px-8" })}
					>
						{block.actionLabel}
					</a>
				) : null}
			</div>
		</section>
	);
}
