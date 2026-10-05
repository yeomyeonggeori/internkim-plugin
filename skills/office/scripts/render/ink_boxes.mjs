const atomicSelector = "img, svg, canvas, video, [data-chart], [data-native-chart]";

const area = (rect) => Math.max(0, rect.right - rect.left) * Math.max(0, rect.bottom - rect.top);

const intersectionArea = (first, second) =>
  area({ left: Math.max(first.left, second.left), top: Math.max(first.top, second.top), right: Math.min(first.right, second.right), bottom: Math.min(first.bottom, second.bottom) });

const extentPast = (rect, container) => Math.max(rect.right - container.right, rect.bottom - container.bottom, container.left - rect.left, container.top - rect.top);

const emBand = (rect, emHeight) => {
  const middle = (rect.top + rect.bottom) / 2;
  return rect.bottom - rect.top > emHeight && emHeight > 0 ? { ...rect, top: middle - emHeight / 2, bottom: middle + emHeight / 2 } : rect;
};

const toRect = (rect) => ({ left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom });

export function measureInkBoxes(page, tools, { relation, tolerance, minimumArea, backdropShare }) {
  const { describe, elementsOf, ownTextRects, isPainted } = tools;
  const frame = toRect(page.getBoundingClientRect());
  const frameArea = area(frame);

  const textRectsOf = (element) => {
    const emHeight = parseFloat(getComputedStyle(element).fontSize) || 0;
    return ownTextRects(element).map((rect) => emBand(toRect(rect), emHeight));
  };

  const boxRectsOf = (element) => {
    const box = toRect(element.getBoundingClientRect());
    const isBox = element.matches(atomicSelector) || (isPainted(element) && !getComputedStyle(element).display.startsWith("inline"));
    return isBox && area(box) > 0 ? [box] : [];
  };

  const parts = elementsOf(page)
    .slice(1)
    .filter((element) => !element.parentElement.closest(atomicSelector))
    .map((element) => ({ element, textRects: textRectsOf(element), rects: [...textRectsOf(element), ...boxRectsOf(element)], box: toRect(element.getBoundingClientRect()) }))
    .filter((part) => part.rects.length > 0);

  const isContainer = (element) => {
    const style = getComputedStyle(element);
    return isPainted(element) || [style.overflowX, style.overflowY, style.overflow].some((value) => value && value !== "visible");
  };

  const isBackdrop = (part) => isPainted(part.element) || part.element.matches(atomicSelector) ? area(part.box) >= frameArea * backdropShare : false;

  const flag = (part, detail) => ({ ...describe(part.element), detail });

  const outermost = (offenders) => offenders.filter((part) => !offenders.some((other) => other !== part && other.element.contains(part.element)));

  const measures = {
    frame: () => {
      const offenders = parts.filter((part) => part.rects.some((rect) => extentPast(rect, frame) > tolerance));
      return outermost(offenders).map((part) => flag(part, `${Math.round(Math.max(...part.rects.map((rect) => extentPast(rect, frame))))}px past the slide's edge`));
    },

    container: () => {
      const containers = elementsOf(page).slice(1).filter(isContainer).map((element) => ({ element, box: toRect(element.getBoundingClientRect()) }));
      const violations = parts.flatMap((part) => {
        const holders = containers.filter((holder) => holder.element.contains(part.element));
        const inkWithin = (holder) => (holder.element === part.element ? part.textRects : part.rects);
        const broken = holders.map((holder) => ({ part, holder, past: Math.max(-Infinity, ...inkWithin(holder).map((rect) => extentPast(rect, holder.box))) })).filter((violation) => violation.past > tolerance);
        return broken.length ? [broken.reduce((innermost, violation) => (innermost.holder.element.contains(violation.holder.element) ? violation : innermost))] : [];
      });
      const reported = outermost(violations.map((violation) => violation.part));
      return violations.filter((violation) => reported.includes(violation.part)).map(({ part, holder, past }) => flag(part, `${Math.round(past)}px past ${describe(holder.element).selector}, which should hold it`));
    },

    sibling: () => {
      const candidates = parts.filter((part) => !isBackdrop(part));
      return candidates.flatMap((first, index) =>
        candidates.slice(index + 1).flatMap((second) => {
          if (first.element.contains(second.element) || second.element.contains(first.element)) return [];
          const covers = first.rects.some((one) => second.rects.some((other) => intersectionArea(one, other) >= minimumArea));
          if (!covers) return [];
          const name = describe(second.element);
          return [flag(first, `covers or is covered by ${name.selector}${name.text ? ` "${name.text.slice(0, 24)}"` : ""}`)];
        }),
      );
    },
  };

  return measures[relation]();
}
