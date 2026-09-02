import type { ReactNode } from "react";

const EMAIL_PATTERN = /[\w.+-]+@[\w-]+\.[\w.-]+/g;
const URL_PATTERN = /https?:\/\/[^\s<>"')]+/g;
const INSTAGRAM_HANDLE_PATTERN = /@[\w.]{2,30}/g;

const LINKABLE_PATTERN = new RegExp(
	`(${EMAIL_PATTERN.source})|(${URL_PATTERN.source})|(${INSTAGRAM_HANDLE_PATTERN.source})`,
	"g",
);

export function autoLink(text: string): ReactNode[] {
	const nodes: ReactNode[] = [];
	let lastIndex = 0;
	for (const match of text.matchAll(LINKABLE_PATTERN)) {
		const matchedText = match[0];
		const matchIndex = match.index ?? 0;
		if (matchIndex > lastIndex) nodes.push(text.slice(lastIndex, matchIndex));
		nodes.push(linkFor(matchedText, matchIndex));
		lastIndex = matchIndex + matchedText.length;
	}
	if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
	return nodes;
}

function linkFor(matchedText: string, key: number): ReactNode {
	const className = "font-medium underline underline-offset-4 transition-colors hover:text-foreground";
	if (matchedText.includes("@") && !matchedText.startsWith("@")) {
		return (
			<a key={key} href={`mailto:${matchedText}`} className={className}>
				{matchedText}
			</a>
		);
	}
	if (matchedText.startsWith("http")) {
		return (
			<a key={key} href={matchedText} target="_blank" rel="noreferrer" className={className}>
				{matchedText}
			</a>
		);
	}
	return (
		<a key={key} href={`https://instagram.com/${matchedText.slice(1)}`} target="_blank" rel="noreferrer" className={className}>
			{matchedText}
		</a>
	);
}
