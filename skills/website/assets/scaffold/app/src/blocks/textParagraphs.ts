export function normalizeEscapedNewlines(text: string): string {
	return text.replace(/\\n/g, "\n");
}

export function splitParagraphs(body: string | undefined): string[] {
	if (!body) return [];
	return normalizeEscapedNewlines(body)
		.split(/\n{2,}/)
		.filter((paragraph) => paragraph.trim().length > 0);
}
