from __future__ import annotations

from dataclasses import dataclass
import colorsys
import math
import re


BLACK = (0.0, 0.0, 0.0)
FUNCTION_PATTERN = re.compile(r"^([a-z-]+)\((.*)\)$")


@dataclass(frozen=True)
class Color:
    hex_value: str
    alpha: float


def parse_css_color(text: str) -> Color:
    value = text.strip().casefold()
    if value == "transparent":
        return Color("000000", 0.0)
    if value.startswith("#"):
        return hex_color(value[1:])
    match = FUNCTION_PATTERN.match(value)
    if not match:
        return Color("000000", 1.0)
    name, arguments = match.groups()
    if name == "color":
        arguments = arguments.partition(" ")[2]
    components, alpha = color_arguments(arguments)
    return Color(hex_of(red_green_blue(name, components)), alpha)


def hex_color(digits: str) -> Color:
    if len(digits) in (3, 4):
        digits = "".join(digit * 2 for digit in digits)
    alpha = int(digits[6:8], 16) / 255 if len(digits) == 8 else 1.0
    return Color(digits[:6].upper(), alpha)


def color_arguments(arguments: str) -> tuple[list[str], float]:
    channel_text, _, alpha_text = arguments.replace(",", " ").partition("/")
    channels = channel_text.split()
    if not alpha_text and len(channels) == 4:
        alpha_text = channels.pop()
    return channels, fraction(alpha_text) if alpha_text.strip() else 1.0


def fraction(text: str) -> float:
    text = text.strip()
    if text.endswith("%"):
        return float(text[:-1]) / 100
    return float(text)


def red_green_blue(name: str, channels: list[str]) -> tuple[float, float, float]:
    if name in ("rgb", "rgba"):
        return tuple(fraction(channel) if channel.endswith("%") else float(channel) / 255 for channel in channels)
    if name in ("hsl", "hsla"):
        hue, saturation, lightness = float(channels[0].removesuffix("deg")) / 360, fraction(channels[1]), fraction(channels[2])
        return colorsys.hls_to_rgb(hue % 1, lightness, saturation)
    if name == "color":
        return tuple(fraction(channel) for channel in channels)
    if name == "oklab":
        return oklab_to_srgb(fraction(channels[0]), float(channels[1]), float(channels[2]))
    if name == "oklch":
        lightness, chroma, hue = fraction(channels[0]), float(channels[1]), math.radians(float(channels[2].removesuffix("deg")))
        return oklab_to_srgb(lightness, chroma * math.cos(hue), chroma * math.sin(hue))
    return BLACK


def oklab_to_srgb(lightness: float, a: float, b: float) -> tuple[float, float, float]:
    long_cone = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    medium_cone = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    short_cone = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    linear = (
        4.0767416621 * long_cone - 3.3077115913 * medium_cone + 0.2309699292 * short_cone,
        -1.2684380046 * long_cone + 2.6097574011 * medium_cone - 0.3413193965 * short_cone,
        -0.0041960863 * long_cone - 0.7034186147 * medium_cone + 1.7076147010 * short_cone,
    )
    return tuple(gamma_encoded(channel) for channel in linear)


def gamma_encoded(linear: float) -> float:
    if linear <= 0.0031308:
        return 12.92 * linear
    return 1.055 * linear ** (1 / 2.4) - 0.055


def hex_of(channels: tuple[float, float, float]) -> str:
    return "".join(f"{round(min(1.0, max(0.0, channel)) * 255):02X}" for channel in channels)


def relative_luminance(hex_value: str) -> float:
    channels = [int(hex_value.lstrip("#")[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def most_contrasting(candidates: list[str], backdrop: str) -> str:
    return max(candidates, key=lambda candidate: contrast_ratio(parse_css_color(candidate).hex_value, parse_css_color(backdrop).hex_value))
