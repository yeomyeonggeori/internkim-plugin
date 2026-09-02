import { buttonVariants } from "../components/ui/button";
import type { Block } from "../site-content";
import { autoLink } from "./autoLink";
import { resolveBlockIcon } from "./blockIcons";
import { normalizeEscapedNewlines, splitParagraphs } from "./textParagraphs";

type ContactProps = {
	block: Block;
	anchorID: string;
};

export function Contact({ block, anchorID }: ContactProps) {
	const items = block.items ?? [];
	return (
		<section id={anchorID} className="py-20">
			<div className="surface-card px-8 py-12 sm:px-12">
				{block.title ? <h2 className="text-3xl font-bold tracking-tight">{block.title}</h2> : null}
				{splitParagraphs(block.body).map((paragraph, paragraphIndex) => (
					<p key={paragraphIndex} className="mt-4 max-w-2xl text-lg leading-relaxed text-muted-foreground">
						{autoLink(paragraph)}
					</p>
				))}
				{items.length > 0 ? (
					<dl className="mt-8 grid gap-5 sm:grid-cols-2">
						{items.map((item, itemIndex) => {
							const ItemIcon = resolveBlockIcon(item.icon);
							return (
								<div key={itemIndex} className="flex items-start gap-3">
									{ItemIcon ? (
										<span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-accent">
											<ItemIcon className="h-4 w-4" />
										</span>
									) : null}
									<div>
										<dt className="text-sm font-semibold">{item.title}</dt>
										<dd className="mt-1 whitespace-pre-line leading-relaxed text-muted-foreground">{autoLink(normalizeEscapedNewlines(item.body))}</dd>
									</div>
								</div>
							);
						})}
					</dl>
				) : null}
				{block.actionLabel ? (
					<a href={block.actionHref ?? "#"} className={buttonVariants({ size: "lg", className: "mt-8 px-8" })}>
						{block.actionLabel}
					</a>
				) : null}
			</div>
		</section>
	);
}
