const isWhitespace = (character) => /\s/u.test(character);

const isEastAsian = (word) => /[　-鿿가-힯]/u.test(word);

const isDigit = (character) => /\p{N}/u.test(character);

const isInline = (element) => getComputedStyle(element).display === "inline";

const inlineTextNodes = (block) =>
  Array.from(block.childNodes).flatMap((node) => {
    if (node.nodeType === Node.TEXT_NODE) return [node];
    if (node.nodeType === Node.ELEMENT_NODE && isInline(node)) return inlineTextNodes(node);
    return [];
  });

const placedCharacters = (node) => {
  const range = document.createRange();
  return Array.from(node.textContent).map((character, offset) => {
    if (isWhitespace(character)) return { character, node, rect: null };
    range.setStart(node, offset);
    range.setEnd(node, offset + 1);
    return { character, node, rect: range.getClientRects()[0] || null };
  });
};

const isBelow = (following, preceding) => (following.rect.top + following.rect.bottom) / 2 > preceding.rect.bottom;

const lineCount = (characters) => 1 + characters.slice(1).filter((placed, index) => isBelow(placed, characters[index])).length;

const linesOf = (characters) =>
  characters.reduce((lines, placed, index) => {
    if (index > 0 && isBelow(placed, characters[index - 1])) return [...lines, [placed]];
    lines.at(-1).push(placed);
    return lines;
  }, [[]]);

const startsAnotherWord = (preceding, placed) =>
  isEastAsian(preceding.character) !== isEastAsian(placed.character) ||
  (preceding.node !== placed.node && isDigit(preceding.character) && isDigit(placed.character));

const wordsOf = (stream) =>
  stream.reduce((words, placed) => {
    if (!placed.rect) return isWhitespace(placed.character) && words.at(-1).length ? [...words, []] : words;
    const preceding = words.at(-1).at(-1);
    if (preceding && startsAnotherWord(preceding, placed)) return [...words, [placed]];
    words.at(-1).push(placed);
    return words;
  }, [[]]).filter((word) => word.length > 0);

const textBlocks = (page, elementsOf) =>
  elementsOf(page)
    .slice(1)
    .filter((element) => !element.closest("aside") && !isInline(element))
    .map((block) => ({ block, stream: inlineTextNodes(block).flatMap(placedCharacters) }))
    .filter(({ stream }) => stream.some((placed) => placed.rect));

export function measureBrokenWords(page, { describe, elementsOf }, { maximumCharacters }) {
  return textBlocks(page, elementsOf).flatMap(({ block, stream }) =>
    wordsOf(stream)
      .map((word) => ({ word, text: word.map((placed) => placed.character).join("") }))
      .filter(({ word, text }) => text.length >= 2 && text.length <= maximumCharacters && !isEastAsian(text) && lineCount(word) > 1)
      .map(({ text }) => ({ ...describe(block), detail: `"${text}" is split across two lines` })),
  );
}

const followsASpace = (stream, placed) => {
  const position = stream.indexOf(placed);
  return position > 0 && isWhitespace(stream[position - 1].character);
};

const largestTextSize = (block) => Math.max(...inlineTextNodes(block).map((node) => parseFloat(getComputedStyle(node.parentElement).fontSize) || 0));

const displaySizeOf = (page) => {
  const probe = document.createElement("i");
  probe.style.setProperty("font-size", "var(--size-display)");
  page.appendChild(probe);
  const size = parseFloat(getComputedStyle(probe).fontSize) || Infinity;
  probe.remove();
  return size;
};

export function measureLineRunts(page, { describe, elementsOf }, { maximumCharacters }) {
  const displaySize = displaySizeOf(page);
  return textBlocks(page, elementsOf).flatMap(({ block, stream }) => {
    const lines = linesOf(stream.filter((placed) => placed.rect));
    const last = lines.at(-1);
    const text = last.map((placed) => placed.character).join("");
    if (lines.length < 2 || text.length > maximumCharacters || !followsASpace(stream, last[0])) return [];
    const severity = largestTextSize(block) >= displaySize ? {} : { severity: "warning" };
    return [{ ...describe(block), ...severity, detail: `its text wraps onto ${lines.length} lines and the last holds only "${text}"` }];
  });
}
