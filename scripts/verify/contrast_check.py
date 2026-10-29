"""WCAG 2.2 contrast of the proposed light theme's colour pairs (docs/design-direction-light.md).
Report only.

Text needs at least 4.5:1 against its background, icons, control borders and focus rings at least
3:1 (WCAG 1.4.3 and 1.4.11). Exits 1 when a pair falls short.

    uv run python -m scripts.verify.contrast_check
"""

import sys

TEXT, UI = 4.5, 3.0
CANVAS, PAPER = "#F5F6F8", "#FFFFFF"

# (pair, foreground, background, minimum)
PAIRS = [
    ("body text on canvas", "#2B2F38", CANVAS, TEXT),
    ("body text on paper", "#2B2F38", PAPER, TEXT),
    ("muted text on canvas", "#5B6170", CANVAS, TEXT),
    ("muted text on paper", "#5B6170", PAPER, TEXT),
    ("heading indigo on paper", "#1B1464", PAPER, TEXT),
    ("link and primary on paper", "#2442D6", PAPER, TEXT),
    ("link and primary on canvas", "#2442D6", CANVAS, TEXT),
    ("white text on primary", "#FFFFFF", "#2442D6", TEXT),
    ("white text on primary hover", "#FFFFFF", "#1A2FA3", TEXT),
    ("link on brand tint", "#2442D6", "#E8ECFF", TEXT),
    ("control border on paper", "#7A8091", PAPER, UI),
    ("focus ring on paper", "#1B1464", PAPER, UI),
    ("approve text on its tint", "#2E6B1F", "#E3F0DA", TEXT),
    ("approve icon on its tint", "#3F8A2A", "#E3F0DA", UI),
    ("pend text on its tint", "#7A5300", "#FFF2CC", TEXT),
    ("pend icon on its tint", "#9A6A00", "#FFF2CC", UI),
    ("deny text on its tint", "#A1121B", "#FCE4E4", TEXT),
    ("deny icon on its tint", "#B3141F", "#FCE4E4", UI),
    ("rejected text on its tint", "#474D5B", "#ECEEF2", TEXT),
    ("in review text on its tint", "#1B1464", "#E8ECFF", TEXT),
]


def luminance(colour: str) -> float:
    channels = [int(colour.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(foreground: str, background: str) -> float:
    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def main() -> None:
    short = []
    for name, foreground, background, minimum in PAIRS:
        found = ratio(foreground, background)
        ok = found >= minimum
        short += [] if ok else [name]
        mark = "ok  " if ok else "FAIL"
        print(f"{mark} {found:5.2f}:1 (min {minimum}) {name}: {foreground} on {background}")
    sys.exit(1 if short else 0)


if __name__ == "__main__":
    main()
