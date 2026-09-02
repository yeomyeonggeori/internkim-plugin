import type { Block } from "../site-content";
import { splitParagraphs } from "./textParagraphs";

type ProseProps = {
	block: Block;
	anchorID: string;
};

export function Prose({ block, anchorID }: ProseProps) {
	const paragraphs = splitParagraphs(block.body);
	return (
		<section id={anchorID} className="py-20">
			{block.image ? (
				<img
					src={block.image}
					alt={block.imageAlt ?? ""}
					className="mb-10 max-h-[24rem] w-full rounded-[calc(var(--radius-lg)*1.5)] object-cover"
				/>
			) : null}
			<div className="grid gap-8 md:grid-cols-[minmax(0,16rem)_1fr]">
				{block.title ? <h2 className="text-3xl font-bold leading-tight tracking-tight">{block.title}</h2> : null}
				<div className={block.title ? "" : "md:col-span-2"}>
					{paragraphs.map((paragraph, paragraphIndex) => (
						<p
							key={paragraphIndex}
							className={
								(paragraphIndex === 0 ? "prose-lede" : "mt-5 leading-[1.85] text-muted-foreground") +
								" max-w-[42rem] whitespace-pre-line"
							}
						>
							{paragraph}
						</p>
					))}
				</div>
			</div>
		</section>
	);
}
