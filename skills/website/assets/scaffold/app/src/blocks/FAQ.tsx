import { ChevronDown } from "lucide-react";
import type { Block } from "../site-content";
import { normalizeEscapedNewlines } from "./textParagraphs";

type FAQProps = {
	block: Block;
	anchorID: string;
};

export function FAQ({ block, anchorID }: FAQProps) {
	const items = block.items ?? [];
	return (
		<section id={anchorID} className="py-20">
			{block.title ? <h2 className="text-3xl font-bold tracking-tight">{block.title}</h2> : null}
			<div className="surface-card mt-8 divide-y divide-border overflow-hidden !p-0">
				{items.map((item, itemIndex) => (
					<details key={itemIndex} className="group px-7 py-5">
						<summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium [&::-webkit-details-marker]:hidden">
							{item.title}
							<ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
						</summary>
						<p className="mt-3 whitespace-pre-line leading-relaxed text-muted-foreground">{normalizeEscapedNewlines(item.body)}</p>
					</details>
				))}
			</div>
		</section>
	);
}
