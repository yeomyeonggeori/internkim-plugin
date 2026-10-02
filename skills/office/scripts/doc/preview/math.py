from __future__ import annotations


MATH_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/math"
MATH_TAGS = (f"{{{MATH_NAMESPACE}}}oMath", f"{{{MATH_NAMESPACE}}}oMathPara")
SCRIPT_MARKS = {"sup": "^", "sub": "_"}


def math_tag(name: str) -> str:
    return f"{{{MATH_NAMESPACE}}}{name}"


def linear_math(element) -> str:
    name = element.tag.split("}", 1)[-1]
    if name == "t":
        return element.text or ""
    if name == "f":
        return f"{grouped(element, 'num')}/{grouped(element, 'den')}"
    if name in ("sSup", "sSub", "sSubSup"):
        return part(element, "e") + "".join(SCRIPT_MARKS[script] + grouped(element, script) for script in ("sub", "sup") if element.find(math_tag(script)) is not None)
    if name == "rad":
        return f"{part(element, 'deg')}√({part(element, 'e')})"
    if name == "nary":
        return nary_symbol(element) + "".join(SCRIPT_MARKS[script] + grouped(element, script) for script in ("sub", "sup") if part(element, script)) + " " + part(element, "e")
    if name == "d":
        return delimited(element)
    if name.endswith("Pr"):
        return ""
    return "".join(linear_math(child) for child in element)


def part(element, name: str) -> str:
    found = element.find(math_tag(name))
    return linear_math(found) if found is not None else ""


def grouped(element, name: str) -> str:
    text = part(element, name)
    return text if len(text) <= 1 else f"({text})"


def nary_symbol(element) -> str:
    character = element.find(f"{math_tag('naryPr')}/{math_tag('chr')}")
    return character.get(math_tag("val")) if character is not None else "∫"


def delimited(element) -> str:
    properties = element.find(math_tag("dPr"))
    inner = delimiter(properties, "sepChr", ",").join(linear_math(child) for child in element.findall(math_tag("e")))
    return delimiter(properties, "begChr", "(") + inner + delimiter(properties, "endChr", ")")


def delimiter(properties, name: str, default: str) -> str:
    found = properties.find(math_tag(name)) if properties is not None else None
    return found.get(math_tag("val"), default) if found is not None else default
