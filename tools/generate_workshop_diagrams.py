#!/usr/bin/env python3
"""Workshop schematic PNGs using Red Hat Display and Red Hat Text.

Typography follows Red Hat brand standards:
https://www.redhat.com/en/about/brand/standards/typography

- Display for titles (>= 18 px); Text for body (< 18 px)
- Sentence case; no ALL CAPS; default tracking
- Left-aligned body; generous whitespace
- One emphasis at a time (weight or color, not both stacked)
"""

from __future__ import annotations

import math
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = Path(__file__).resolve().parent / ".fonts"
OUT_DIR = ROOT / "content/modules/ROOT/assets/images"

# Official Red Hat digital palette.
RED = (238, 0, 0)  # #EE0000
BLACK = (21, 21, 21)  # #151515
GRAY = (106, 110, 115)  # #6A6E73
LINE = (210, 210, 210)  # #D2D2D2
BAND = (248, 248, 248)
WHITE = (255, 255, 255)
CANVAS = (255, 255, 255)

FONT_URLS = {
    "RedHatDisplay-Medium.ttf": (
        "https://raw.githubusercontent.com/RedHatOfficial/RedHatFont/master/"
        "fonts/Proportional/RedHatDisplay/ttf/RedHatDisplay-Medium.ttf"
    ),
    "RedHatDisplay-Regular.ttf": (
        "https://raw.githubusercontent.com/RedHatOfficial/RedHatFont/master/"
        "fonts/Proportional/RedHatDisplay/ttf/RedHatDisplay-Regular.ttf"
    ),
    "RedHatText-Regular.ttf": (
        "https://raw.githubusercontent.com/RedHatOfficial/RedHatFont/master/"
        "fonts/Proportional/RedHatText/ttf/RedHatText-Regular.ttf"
    ),
    "RedHatText-Medium.ttf": (
        "https://raw.githubusercontent.com/RedHatOfficial/RedHatFont/master/"
        "fonts/Proportional/RedHatText/ttf/RedHatText-Medium.ttf"
    ),
    "RedHatMono-Regular.ttf": (
        "https://raw.githubusercontent.com/RedHatOfficial/RedHatFont/master/"
        "fonts/Mono/RedHatMono/ttf/RedHatMono-Regular.ttf"
    ),
}

_FONTS: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def ensure_fonts() -> None:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in FONT_URLS.items():
        path = FONT_DIR / name
        if path.exists() and path.stat().st_size > 1000:
            continue
        urllib.request.urlretrieve(url, path)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    key = (name, size)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(str(FONT_DIR / name), size)
    return _FONTS[key]


class Board:
    def __init__(self, w: int, h: int):
        self.w = w
        self.h = h
        # Render at 2x then downsample for clean geometry and type.
        self.scale = 2
        self.img = Image.new("RGB", (w * self.scale, h * self.scale), CANVAS)
        self.draw = ImageDraw.Draw(self.img)

    def s(self, v: float) -> int:
        return int(round(v * self.scale))

    def display(self, size: int) -> ImageFont.FreeTypeFont:
        return font("RedHatDisplay-Medium.ttf", int(size * self.scale))

    def body(self, size: int) -> ImageFont.FreeTypeFont:
        return font("RedHatText-Regular.ttf", int(size * self.scale))

    def width(self, s: str, fnt: ImageFont.FreeTypeFont) -> float:
        box = self.draw.textbbox((0, 0), s, font=fnt)
        return (box[2] - box[0]) / self.scale

    def line_h(self, fnt: ImageFont.FreeTypeFont) -> float:
        ascent, descent = fnt.getmetrics()
        return (ascent + descent) / self.scale

    def save(self, path: Path) -> None:
        out = self.img.resize((self.w, self.h), Image.Resampling.LANCZOS)
        path.parent.mkdir(parents=True, exist_ok=True)
        out.save(path, "PNG", optimize=True)
        print(f"wrote {path.relative_to(ROOT)} ({self.w}x{self.h})")

    def frame(self) -> None:
        self.draw.rectangle([0, 0, self.s(8), self.img.height], fill=RED)

    def text(
        self,
        xy: tuple[float, float],
        s: str,
        fnt: ImageFont.FreeTypeFont,
        fill=BLACK,
        anchor: str = "lt",
    ) -> None:
        self.draw.text((self.s(xy[0]), self.s(xy[1])), s, font=fnt, fill=fill, anchor=anchor)

    def line(self, a, b, fill=BLACK, width: float = 1.5) -> None:
        self.draw.line(
            [self.s(a[0]), self.s(a[1]), self.s(b[0]), self.s(b[1])],
            fill=fill,
            width=max(1, self.s(width)),
        )

    def dashed(self, a, b, fill=GRAY, width: float = 1.25, dash: float = 8, gap: float = 6) -> None:
        x1, y1 = a
        x2, y2 = b
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1
        ux, uy = dx / length, dy / length
        pos = 0.0
        on = True
        while pos < length:
            step = dash if on else gap
            nxt = min(pos + step, length)
            if on:
                self.line(
                    (x1 + ux * pos, y1 + uy * pos),
                    (x1 + ux * nxt, y1 + uy * nxt),
                    fill=fill,
                    width=width,
                )
            pos = nxt
            on = not on

    def arrow(self, a, b, fill=BLACK, width: float = 1.5, head: float = 10) -> None:
        x1, y1 = a
        x2, y2 = b
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1
        ux, uy = dx / length, dy / length
        tip = (x2, y2)
        base = (x2 - ux * head, y2 - uy * head)
        self.line(a, base, fill=fill, width=width)
        px, py = -uy, ux
        p1 = (base[0] + px * head * 0.42, base[1] + py * head * 0.42)
        p2 = (base[0] - px * head * 0.42, base[1] - py * head * 0.42)
        self.draw.polygon(
            [
                self.s(tip[0]),
                self.s(tip[1]),
                self.s(p1[0]),
                self.s(p1[1]),
                self.s(p2[0]),
                self.s(p2[1]),
            ],
            fill=fill,
        )

    def rounded(self, box, radius: float, fill=WHITE, outline=LINE, width: float = 1) -> None:
        x0, y0, x1, y1 = box
        self.draw.rounded_rectangle(
            [self.s(x0), self.s(y0), self.s(x1), self.s(y1)],
            radius=self.s(radius),
            fill=fill,
            outline=outline,
            width=max(1, self.s(width)),
        )

    def accent_bar(self, box, width: float = 5) -> None:
        x0, y0, _x1, y1 = box
        self.draw.rectangle(
            [self.s(x0), self.s(y0 + 6), self.s(x0 + width), self.s(y1 - 6)],
            fill=RED,
        )

    def wrap(self, s: str, fnt: ImageFont.FreeTypeFont, max_w: float) -> list[str]:
        words = s.split()
        lines: list[str] = []
        cur = ""
        for word in words:
            trial = f"{cur} {word}".strip()
            if self.width(trial, fnt) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines or [s]

    def card(self, box, title: str, subtitle: str, pad: float = 22) -> None:
        self.rounded(box, radius=6, fill=WHITE, outline=LINE, width=1)
        self.accent_bar(box)
        x0, y0, x1, _y1 = box
        tx = x0 + pad + 6
        max_w = (x1 - tx) - pad
        title_f = self.display(22)
        sub_f = self.body(16)
        y = y0 + pad + 2
        for line in self.wrap(title, title_f, max_w):
            self.text((tx, y), line, title_f, fill=BLACK)
            y += self.line_h(title_f) + 2
        y += 6
        for line in self.wrap(subtitle, sub_f, max_w):
            self.text((tx, y), line, sub_f, fill=GRAY)
            y += self.line_h(sub_f) + 2

    def band(self, box) -> None:
        self.rounded(box, radius=10, fill=BAND, outline=BAND, width=0)

    def footer(self, caption: str, y: float | None = None) -> None:
        y = self.h - 56 if y is None else y
        self.line((48, y), (self.w - 48, y), fill=RED, width=2)
        self.text((48, y + 18), "Red Hat", self.display(18), fill=BLACK)
        self.text((self.w - 48, y + 18), caption, self.body(16), fill=GRAY, anchor="rt")

    def title(self, s: str, y: float = 36) -> None:
        self.text((48, y), s, self.display(34), fill=BLACK)


def architecture() -> None:
    b = Board(1680, 980)
    b.frame()
    b.title("In-cluster coding agent on ROSA")

    b.band((48, 100, 1632, 340))
    b.text((72, 118), "Act 1 — platform", b.display(18), fill=RED)
    cards = [
        (72, 160, 520, 308, "ROSA HCP", "workers + 1× L40S GPU"),
        (612, 160, 1060, 308, "OpenShift AI MaaS", "Qwen3.8-27B INT4"),
        (1152, 160, 1600, 308, "Gateway maas.apps…", "one sk-oai- API key"),
    ]
    for x0, y0, x1, y1, t, s in cards:
        b.card((x0, y0, x1, y1), t, s)
    b.arrow((520, 234), (612, 234))
    b.arrow((1060, 234), (1152, 234))

    b.band((48, 368, 1632, 668))
    b.text((72, 386), "Act 2 — developer", b.display(18), fill=RED)
    cards2 = [
        (72, 428, 520, 576, "Dev Spaces", "browser IDE"),
        (612, 428, 1060, 576, "OpenCode + AGENTS.md", "~45-line runbook"),
        (1152, 428, 1600, 576, "Fortune Cookie app", "Go, Tekton, Argo CD"),
    ]
    for x0, y0, x1, y1, t, s in cards2:
        b.card((x0, y0, x1, y1), t, s)
    b.arrow((520, 502), (612, 502))
    b.arrow((1060, 502), (1152, 502))

    # OpenCode talks to the gateway (inter-band, so the line does not cross Fortune Cookie).
    src = (900, 428)
    dst = (1376, 308)
    b.dashed(src, dst, fill=GRAY, width=1.25)
    b.arrow(src, dst, fill=GRAY, width=1.25, head=9)
    b.text((980, 348), "chat completions", b.body(15), fill=GRAY)

    b.band((48, 696, 1632, 868))
    b.text((72, 714), "Act 3 — the bill", b.display(18), fill=RED)
    b.card((72, 754, 1600, 848), "GPU metrics + token quota", "DCGM + MaaS subscription")

    b.footer("The LLM writes the app. The app does not call the LLM.")
    b.save(OUT_DIR / "architecture-overview.png")


def model_serving() -> None:
    b = Board(1680, 720)
    b.frame()
    b.title("Qwen3.8 as Models-as-a-Service")

    client = (72, 200, 500, 360)
    gw = (616, 160, 1064, 320)
    llm = (1180, 200, 1608, 360)
    dash = (616, 420, 1064, 560)

    b.card(client, "OpenCode / curl", "Authorization: Bearer sk-oai-…")
    b.card(gw, "Gateway maas.<apps-domain>", "Authorino auth + Limitador quota")
    b.card(llm, "LLMInferenceService qwen3", "Red Hat vLLM on L40S")
    b.card(dash, "Dashboard rh-ai.apps…", "catalog, extra keys")

    b.arrow((500, 280), (616, 240))
    b.text((508, 188), "HTTPS OpenAI API", b.body(15), fill=GRAY)
    b.arrow((1064, 240), (1180, 280))
    b.text((1076, 188), "TLS to GPU", b.body(15), fill=GRAY)
    b.line((840, 320), (840, 420), fill=GRAY, width=1.25)

    b.footer("One front door. One API key. GitOps owns the serving stack.")
    b.save(OUT_DIR / "model-serving-architecture.png")


def cicd() -> None:
    b = Board(1760, 680)
    b.frame()
    b.title("Prompt to production")

    steps = [
        ("1", "Prompt OpenCode", "reads AGENTS.md"),
        ("2", "Ephemeral Git", "personal repo"),
        ("3", "Tekton PipelineRun", "git-clone + buildah"),
        ("4", "Argo CD", "developer instance"),
        ("5", "HTTPS Route", "Fortune Cookie live"),
    ]
    n = len(steps)
    margin = 56
    gap = 36
    usable = b.w - margin * 2
    cw = (usable - gap * (n - 1)) / n
    y0, y1 = 230, 470
    boxes = []
    for i, (num, title, sub) in enumerate(steps):
        x0 = margin + i * (cw + gap)
        x1 = x0 + cw
        box = (x0, y0, x1, y1)
        boxes.append(box)
        b.rounded(box, radius=6, fill=WHITE, outline=LINE, width=1)
        b.accent_bar(box)
        b.text((x0 + 22, y0 + 22), num, b.display(22), fill=RED)
        title_f = b.display(20)
        sub_f = b.body(15)
        max_w = (x1 - x0) - 44
        ty = y0 + 86
        for line in b.wrap(title, title_f, max_w):
            b.text((x0 + 22, ty), line, title_f, fill=BLACK)
            ty += b.line_h(title_f) + 2
        b.text((x0 + 22, ty + 8), sub, sub_f, fill=GRAY)
        if i:
            prev = boxes[i - 1]
            mid_y = (y0 + y1) / 2
            b.arrow((prev[2], mid_y), (x0, mid_y), head=9)

    # Compact MaaS chip above step 1.
    mid_x = (boxes[0][0] + boxes[0][2]) / 2
    chip_w = 200
    call = (mid_x - chip_w / 2, 118, mid_x + chip_w / 2, 186)
    b.rounded(call, radius=6, fill=WHITE, outline=LINE, width=1)
    b.text((mid_x, 140), "Qwen3.8 MaaS", b.display(18), fill=BLACK, anchor="mt")
    b.dashed((mid_x, y0), (mid_x, call[3]), fill=GRAY, width=1.2)
    b.arrow((mid_x, y0), (mid_x, call[3] + 1), fill=GRAY, width=1.2, head=8)

    b.footer("No Ansible. No local Docker. No public LLM.")
    b.save(OUT_DIR / "cicd-gitops.png")


def the_bill() -> None:
    b = Board(1680, 860)
    b.frame()
    b.title("The bill — GPU and tokens")

    left = (72, 140, 700, 720)
    right = (980, 140, 1608, 720)
    b.band(left)
    b.band(right)
    b.text((96, 164), "What you provisioned", b.display(22), fill=BLACK)
    b.text((1004, 164), "What you measure", b.display(22), fill=BLACK)

    left_items = [
        ("g6e.xlarge L40S", "one NVIDIA GPU node"),
        ("Qwen3.8 INT4 in VRAM", "fits a single L40S"),
        ("MaaS subscription", "5M tokens / 24h"),
    ]
    right_items = [
        ("NVIDIA DCGM", "GPU % and watts"),
        ("vLLM", "tokens / sec and TTFT"),
        ("Limitador", "429 when over quota"),
    ]

    def stack(x0, items):
        top = 230
        h = 130
        gap = 22
        for i, (title, sub) in enumerate(items):
            y = top + i * (h + gap)
            b.card((x0, y, x0 + 580, y + h), title, sub)

    stack(96, left_items)
    stack(1004, right_items)

    ay0, ay1 = 400, 500
    ax0, ax1 = 732, 948
    b.rounded((ax0, ay0, ax1, ay1), radius=8, fill=RED, outline=RED, width=0)
    mid = (ay0 + ay1) / 2
    b.draw.polygon(
        [
            b.s(ax1 + 18),
            b.s(mid),
            b.s(ax1),
            b.s(ay0 + 8),
            b.s(ax1),
            b.s(ay1 - 8),
        ],
        fill=RED,
    )
    b.text((ax0 + 16, ay0 + 20), "OpenCode sessions", b.display(18), fill=WHITE)
    b.text((ax0 + 16, ay0 + 50), "this afternoon", b.body(15), fill=WHITE)

    b.footer("Token quota is how the platform team caps cost.")
    b.save(OUT_DIR / "the-bill-observability.png")


def main() -> None:
    ensure_fonts()
    architecture()
    model_serving()
    cicd()
    the_bill()


if __name__ == "__main__":
    main()
