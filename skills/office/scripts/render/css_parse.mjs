const quoteCharacters = new Set(['"', "'"]);

function skipString(text, start) {
  const quote = text[start];
  let index = start + 1;
  while (index < text.length && text[index] !== quote) index += text[index] === "\\" ? 2 : 1;
  return index;
}

function matchingBrace(text, open) {
  let depth = 0;
  for (let index = open; index < text.length; index += 1) {
    if (quoteCharacters.has(text[index])) index = skipString(text, index);
    else if (text[index] === "{") depth += 1;
    else if (text[index] === "}" && --depth === 0) return index;
  }
  return text.length;
}

export function splitTopLevel(text, separator) {
  const parts = [];
  let depth = 0;
  let start = 0;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoteCharacters.has(character)) index = skipString(text, index);
    else if (character === "(" || character === "[") depth += 1;
    else if (character === ")" || character === "]") depth -= 1;
    else if (depth === 0 && character === separator) {
      parts.push(text.slice(start, index));
      start = index + 1;
    }
  }
  parts.push(text.slice(start));
  return parts;
}

export function splitWords(text) {
  const words = [];
  let depth = 0;
  let current = "";
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoteCharacters.has(character)) {
      const end = skipString(text, index);
      current += text.slice(index, end + 1);
      index = end;
      continue;
    }
    if (character === "(") depth += 1;
    if (character === ")") depth -= 1;
    if (depth === 0 && /\s/.test(character)) {
      if (current) words.push(current);
      current = "";
      continue;
    }
    current += character;
  }
  if (current) words.push(current);
  return words;
}

export function parseDeclarations(text) {
  return splitTopLevel(text, ";").flatMap((part) => {
    const colon = part.indexOf(":");
    if (colon < 0) return [];
    const property = part.slice(0, colon).trim();
    const rawValue = part.slice(colon + 1).trim();
    const important = /!\s*important\s*$/i.test(rawValue);
    const value = important ? rawValue.replace(/!\s*important\s*$/i, "").trim() : rawValue;
    if (!property || !value) return [];
    return [{ property: property.startsWith("--") ? property : property.toLowerCase(), value, important }];
  });
}

function blocksOf(text) {
  const blocks = [];
  let index = 0;
  while (index < text.length) {
    const open = text.indexOf("{", index);
    const semicolon = text.indexOf(";", index);
    if (open < 0) break;
    if (semicolon >= 0 && semicolon < open && text.slice(index, semicolon).trim().startsWith("@")) {
      index = semicolon + 1;
      continue;
    }
    const close = matchingBrace(text, open);
    blocks.push({ prelude: text.slice(index, open).trim(), body: text.slice(open + 1, close) });
    index = close + 1;
  }
  return blocks;
}

const nestedAtRules = new Set(["@supports", "@layer", "@document", "@container"]);

export function parseStylesheet(text, mediaMatches) {
  const rules = [];
  const visit = (body) => {
    for (const { prelude, body: blockBody } of blocksOf(body)) {
      const atName = prelude.startsWith("@") ? prelude.split(/[\s(]/)[0].toLowerCase() : "";
      if (atName === "@media") {
        if (mediaMatches(prelude.slice(6).trim())) visit(blockBody);
        continue;
      }
      if (nestedAtRules.has(atName)) {
        visit(blockBody);
        continue;
      }
      if (atName) continue;
      rules.push({ selectors: splitTopLevel(prelude, ",").map((selector) => selector.trim()).filter(Boolean), declarations: parseDeclarations(blockBody) });
    }
  };
  visit(text.replace(/\/\*[\s\S]*?\*\//g, ""));
  return rules;
}

const legacyPseudoElements = new Set(["before", "after", "first-line", "first-letter", "marker", "placeholder", "selection"]);

function readIdentifier(selector, start) {
  let index = start;
  while (index < selector.length && /[\w\-\\ -￿]/.test(selector[index])) index += selector[index] === "\\" ? 2 : 1;
  return index;
}

function readParenthesized(selector, open) {
  let depth = 0;
  for (let index = open; index < selector.length; index += 1) {
    if (quoteCharacters.has(selector[index])) index = skipString(selector, index);
    else if (selector[index] === "(") depth += 1;
    else if (selector[index] === ")" && --depth === 0) return index;
  }
  return selector.length;
}

function maximumSpecificity(argumentText) {
  return Math.max(0, ...splitTopLevel(argumentText, ",").map((selector) => specificityOf(selector.trim()).specificity));
}

function pseudoSpecificity(name, argumentText) {
  if (name === "where") return 0;
  if (name === "is" || name === "not" || name === "has" || name === "matches") return maximumSpecificity(argumentText);
  if ((name === "nth-child" || name === "nth-last-child") && / of /.test(argumentText)) return 1000 + maximumSpecificity(argumentText.split(/ of /)[1]);
  return 1000;
}

export function specificityOf(selector) {
  let specificity = 0;
  let pseudoElement = "";
  let index = 0;
  while (index < selector.length) {
    const character = selector[index];
    if (character === "#") {
      index = readIdentifier(selector, index + 1);
      specificity += 1000000;
    } else if (character === ".") {
      index = readIdentifier(selector, index + 1);
      specificity += 1000;
    } else if (character === "[") {
      index = readParenthesized(selector.replace(/\[/g, "(").replace(/\]/g, ")"), index) + 1;
      specificity += 1000;
    } else if (character === ":") {
      const isElement = selector[index + 1] === ":";
      const nameStart = index + (isElement ? 2 : 1);
      const nameEnd = readIdentifier(selector, nameStart);
      const name = selector.slice(nameStart, nameEnd).toLowerCase();
      index = nameEnd;
      if (isElement || legacyPseudoElements.has(name)) {
        pseudoElement = name;
        specificity += 1;
        continue;
      }
      let argumentText = "";
      if (selector[index] === "(") {
        const close = readParenthesized(selector, index);
        argumentText = selector.slice(index + 1, close);
        index = close + 1;
      }
      specificity += pseudoSpecificity(name, argumentText);
    } else if (/[a-zA-Z]/.test(character)) {
      index = readIdentifier(selector, index);
      specificity += 1;
    } else {
      index += 1;
    }
  }
  return { specificity, pseudoElement };
}

export function withoutPseudoElement(selector) {
  return selector.replace(/::?(before|after|first-line|first-letter|marker|placeholder|selection)\b/gi, "").trim() || "*";
}
