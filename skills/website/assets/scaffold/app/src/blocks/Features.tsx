import type { Block } from "../site-content";
import { resolveBlockIcon } from "./blockIcons";
import { normalizeEscapedNewlines } from "./textParagraphs";

type FeaturesProps = {
	block: Block;
	anchorID: string;
};

export function Features({ block, anchorID }: FeaturesProps) {
	const items = block.items ?? [];
	const everyItemHasIcon = items.length > 0 && items.every((item) => resolveBlockIcon(item.icon) !== undefined);
	return (
		<section id={anchorID} className="py-20">
			{block.title ? <h2 className="text-3xl font-bold tracking-tight">{block.title}</h2> : null}
			{block.body ? <p className="mt-4 max-w-2xl text-lg leading-relaxed text-muted-foreground">{block.body}</p> : null}
			<div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
				{items.map((item, itemIndex) => {
					const ItemIcon = everyItemHasIcon ? resolveBlockIcon(item.icon) : undefined;
					return (
						<div key={itemIndex} className="surface-card flex flex-col gap-3 p-6">
							{ItemIcon ? (
								<span className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-accent">
									<ItemIcon className="h-5 w-5" />
								</span>
							) : (
								<span className="item-index">{String(itemIndex + 1).padStart(2, "0")}</span>
							)}
							<h3 className="text-lg font-semibold leading-snug">{item.title}</h3>
							<p className="whitespace-pre-line leading-relaxed text-muted-foreground">{normalizeEscapedNewlines(item.body)}</p>
						</div>
					);
				})}
			</div>
		</section>
	);
}
