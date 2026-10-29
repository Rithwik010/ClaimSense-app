"""WCAG 2.2 contrast of the light theme's colour pairs (D-UI-7, docs/design-direction-light.md):
the white pages, the blue sidebar and the decision chips. Report only.

Text needs at least 4.5:1 against its background, icons, control borders and focus rings at least
3:1 (WCAG 1.4.3 and 1.4.11). Exits 1 when a pair falls short.

    uv run python -m scripts.verify.contrast_check
"""

import sys

TEXT, UI = 4.5, 3.0
CANVAS, PAPER = "#F4F4F4", "#FFFFFF"

# (pair, foreground, background, minimum)
PAIRS = [
    ("body text on canvas", "#333333", CANVAS, TEXT),
    ("body text on paper", "#333333", PAPER, TEXT),
    ("muted text on canvas", "#5A5A5A", CANVAS, TEXT),
    ("muted text on paper", "#5A5A5A", PAPER, TEXT),
    ("heading indigo on paper", "#110081", PAPER, TEXT),
    ("link and primary on paper", "#0033FF", PAPER, TEXT),
    ("link and primary on canvas", "#0033FF", CANVAS, TEXT),
    ("white text on primary", "#FFFFFF", "#0033FF", TEXT),
    ("white text on primary hover", "#FFFFFF", "#001F99", TEXT),
    ("link on brand tint", "#0033FF", "#E6EBFF", TEXT),
    ("control border on paper", "#7A8091", PAPER, UI),
    ("focus ring on paper", "#110081", PAPER, UI),
    ("approve text on its tint", "#2E6B1F", "#E3F0DA", TEXT),
    ("approve icon on its tint", "#3F8A2A", "#E3F0DA", UI),
    ("pend text on its tint", "#7A5300", "#FFF2CC", TEXT),
    ("pend icon on its tint", "#9A6A00", "#FFF2CC", UI),
    ("deny text on its tint", "#A1121B", "#FCE4E4", TEXT),
    ("deny icon on its tint", "#B3141F", "#FCE4E4", UI),
    ("rejected text on its tint", "#474D5B", "#ECEEF2", TEXT),
    ("in review text on its tint", "#110081", "#E6EBFF", TEXT),
    ("sidebar link on the sidebar blue", "#FFFFFF", "#0033FF", TEXT),
    ("sidebar role label on the sidebar blue", "#CCD6FF", "#0033FF", TEXT),
    ("sidebar page you are on: white on the darker blue", "#FFFFFF", "#001F99", TEXT),
    ("sidebar link on hover: white on the darker blue", "#FFFFFF", "#001F99", TEXT),
    ("focus outline in the sidebar: white on the sidebar blue", "#FFFFFF", "#0033FF", UI),
    ("focus outline on the page: primary on paper", "#0033FF", PAPER, UI),
    ("evidence quote: body text on the highlight", "#333333", "#FFF2CC", TEXT),
    ("evidence underline on the highlight", "#9A6A00", "#FFF2CC", UI),
    ("muted text on a table header", "#5A5A5A", CANVAS, TEXT),
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
