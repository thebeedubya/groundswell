#!/usr/bin/env python3
"""
Groundswell Image Generator — Nano Banana (Gemini) + PIL text overlay.

Generates images for LinkedIn carousels, X posts, and blog headers.
Uses Google's Gemini image generation for base images, then PIL for
text overlays, branding, and carousel assembly.

Usage:
    python3 tools/image_gen.py generate --prompt "..." --output path.png
    python3 tools/image_gen.py carousel --slides '[{"title":"...","body":"..."}]' --output-dir path/
    python3 tools/image_gen.py terminal --text "..." --output path.png
    python3 tools/image_gen.py quote --text "..." --output path.png
    python3 tools/image_gen.py framework --title "..." --points '["..."]' --output path.png
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from _common import emit, fail, DATA_DIR

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    fail("Pillow is required: pip install Pillow")

IMAGE_DIR = os.path.join(DATA_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Constants — Brad's visual signature
# ---------------------------------------------------------------------------

# Dark terminal aesthetic
BG_DARK = (13, 17, 23)       # #0D1117
BG_CARD = (22, 27, 34)       # #161B22
ACCENT_GREEN = (0, 255, 136)  # #00FF88
ACCENT_TEAL = (78, 205, 196)  # #4ECDC4
ACCENT_PURPLE = (189, 147, 249)  # #BD93F9
ACCENT_ORANGE = (255, 184, 108)  # #FFB86C
WHITE = (255, 255, 255)
GRAY = (136, 136, 136)
DIM_GRAY = (68, 68, 68)
DOT_RED = (255, 95, 86)
DOT_YELLOW = (255, 189, 46)
DOT_GREEN = (39, 201, 63)

# LinkedIn carousel: 1080x1350 portrait
CAROUSEL_W = 1080
CAROUSEL_H = 1350

# Square (IG/general): 1080x1080
SQUARE_W = 1080
SQUARE_H = 1080

FONT_CANDIDATES = [
    "JetBrainsMono-Regular", "JetBrains Mono", "SF Mono",
    "SFMono-Regular", "Menlo", "Courier New", "Courier",
]
FONT_BOLD_CANDIDATES = [
    "JetBrainsMono-Bold", "JetBrains Mono Bold", "SF Mono Bold",
    "Menlo-Bold", "Courier New Bold", "Courier",
]
SANS_CANDIDATES = [
    "Inter", "Helvetica Neue", "Helvetica", "Arial", "San Francisco",
]
SANS_BOLD_CANDIDATES = [
    "Inter Bold", "Helvetica Neue Bold", "Helvetica Bold", "Arial Bold",
]


def _load_font(size, bold=False, sans=False):
    """Try to load a font, falling back gracefully."""
    if sans:
        candidates = SANS_BOLD_CANDIDATES if bold else SANS_CANDIDATES
    else:
        candidates = FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    font_paths = [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Courier New.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue
    return ImageFont.load_default()


def _wrap_text(text, font, max_width, draw):
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines


def _line_height(font):
    return font.getmetrics()[0] + font.getmetrics()[1] + 4


def _gen_filename(prefix):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{ts}.png"


def _resolve_output(output_arg, prefix):
    if output_arg:
        out_dir = os.path.dirname(output_arg)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        return output_arg
    return os.path.join(IMAGE_DIR, _gen_filename(prefix))


# ---------------------------------------------------------------------------
# Nano Banana (Gemini) image generation
# ---------------------------------------------------------------------------

def generate_base_image(prompt, width=1080, height=1080, output=None):
    """Generate an image using Gemini's Nano Banana image generation."""
    api_key = os.environ.get("GOOGLE_AI_API_KEY")
    if not api_key:
        fail("GOOGLE_AI_API_KEY not set in environment")

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        fail("google-genai is required: pip install google-genai")

    client = genai.Client(api_key=api_key)

    # Determine aspect ratio from dimensions
    ratio = width / height
    if abs(ratio - 1.0) < 0.1:
        aspect = "1:1"
    elif abs(ratio - 0.8) < 0.1:  # 1080x1350 = 4:5
        aspect = "4:5"
    elif abs(ratio - 1.78) < 0.1:  # 16:9
        aspect = "16:9"
    elif abs(ratio - 0.5625) < 0.1:  # 9:16
        aspect = "9:16"
    else:
        aspect = "4:5"

    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )

    # Extract image from response
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            img = Image.open(BytesIO(part.inline_data.data))
            # Resize to target dimensions
            img = img.resize((width, height), Image.LANCZOS)
            output_path = _resolve_output(output, "generated")
            img.save(output_path, "PNG")
            return output_path

    fail("No image returned from Gemini")


# ---------------------------------------------------------------------------
# PIL-based image types
# ---------------------------------------------------------------------------

def gen_terminal(text, output):
    """Terminal screenshot aesthetic — Brad's visual signature."""
    img = Image.new("RGB", (SQUARE_W, SQUARE_H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Terminal chrome
    bar_height = 60
    draw.rectangle([(0, 0), (SQUARE_W, bar_height)], fill=(30, 33, 40))
    dot_y = bar_height // 2
    for i, color in enumerate([DOT_RED, DOT_YELLOW, DOT_GREEN]):
        cx = 40 + i * 28
        draw.ellipse([(cx - 8, dot_y - 8), (cx + 8, dot_y + 8)], fill=color)

    title_font = _load_font(18)
    draw.text((SQUARE_W // 2, dot_y), "brad@forge — ~", font=title_font, fill=GRAY, anchor="mm")

    # Body
    body_font = _load_font(26)
    margin = 50
    lh = _line_height(body_font)
    prompt = "brad@forge:~$ "
    lines = _wrap_text(prompt + text, body_font, SQUARE_W - margin * 2, draw)

    y = bar_height + 40
    for i, line in enumerate(lines):
        if y + lh > SQUARE_H - 40:
            break
        if i == 0:
            pbbox = draw.textbbox((margin, y), prompt, font=body_font)
            draw.text((margin, y), prompt, font=body_font, fill=ACCENT_TEAL)
            draw.text((pbbox[2], y), line[len(prompt):], font=body_font, fill=ACCENT_GREEN)
        else:
            draw.text((margin, y), line, font=body_font, fill=ACCENT_GREEN)
        y += lh

    # Cursor
    if y + lh < SQUARE_H - 40:
        draw.rectangle([(margin, y + 4), (margin + 14, y + lh - 2)], fill=ACCENT_GREEN)

    # Branding
    brand_font = _load_font(16)
    draw.text((SQUARE_W // 2, SQUARE_H - 30), "Brad Wood • AI Operator", font=brand_font, fill=DIM_GRAY, anchor="mm")

    output_path = _resolve_output(output, "terminal")
    img.save(output_path, "PNG")
    return output_path


def gen_quote(text, attribution, output):
    """Quote card with gradient accent."""
    img = Image.new("RGBA", (SQUARE_W, SQUARE_H), BG_DARK + (255,))
    draw = ImageDraw.Draw(img)

    # Gradient glow
    gradient = Image.new("RGBA", (SQUARE_W, SQUARE_H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gradient)
    for r in range(400, 0, -2):
        alpha = max(0, int(30 * (1 - r / 400)))
        gdraw.ellipse([(-r, -r), (r, r)], fill=ACCENT_PURPLE + (alpha,))
    img = Image.alpha_composite(img, gradient)
    draw = ImageDraw.Draw(img)

    # Quote mark
    qfont = _load_font(200, bold=True)
    draw.text((80, 120), "\u201C", font=qfont, fill=ACCENT_PURPLE + (60,))

    # Text
    body_font = _load_font(34)
    lines = _wrap_text(text, body_font, SQUARE_W - 200, draw)
    lh = _line_height(body_font)
    total_h = len(lines) * lh
    start_y = (SQUARE_H - total_h) // 2

    for i, line in enumerate(lines):
        draw.text((SQUARE_W // 2, start_y + i * lh), line, font=body_font, fill=WHITE, anchor="mm")

    if attribution:
        attr_font = _load_font(24)
        draw.text((SQUARE_W // 2, start_y + total_h + 50), attribution, font=attr_font, fill=ACCENT_PURPLE, anchor="mm")

    brand_font = _load_font(16)
    draw.text((SQUARE_W // 2, SQUARE_H - 30), "Brad Wood • AI Operator", font=brand_font, fill=DIM_GRAY, anchor="mm")

    output_path = _resolve_output(output, "quote")
    img.convert("RGB").save(output_path, "PNG")
    return output_path


def gen_framework(title, points, output):
    """Framework breakdown slide — perfect for LinkedIn carousel individual slides."""
    img = Image.new("RGB", (CAROUSEL_W, CAROUSEL_H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Accent bar at top
    draw.rectangle([(0, 0), (CAROUSEL_W, 6)], fill=ACCENT_GREEN)

    # Title
    title_font = _load_font(42, bold=True, sans=True)
    title_lines = _wrap_text(title, title_font, CAROUSEL_W - 120, draw)
    y = 80
    for line in title_lines:
        draw.text((60, y), line, font=title_font, fill=WHITE)
        y += _line_height(title_font)

    # Divider
    y += 20
    draw.line([(60, y), (CAROUSEL_W - 60, y)], fill=DIM_GRAY, width=1)
    y += 40

    # Points
    point_font = _load_font(28, sans=True)
    num_font = _load_font(32, bold=True, sans=True)
    lh = _line_height(point_font)

    for i, point in enumerate(points):
        if y + lh * 3 > CAROUSEL_H - 100:
            break

        # Number
        num_color = [ACCENT_GREEN, ACCENT_TEAL, ACCENT_PURPLE, ACCENT_ORANGE][i % 4]
        draw.text((60, y), f"{i + 1}.", font=num_font, fill=num_color)

        # Text
        plines = _wrap_text(point, point_font, CAROUSEL_W - 160, draw)
        for pl in plines:
            draw.text((110, y + 4), pl, font=point_font, fill=WHITE)
            y += lh
        y += 20

    # Branding
    brand_font = _load_font(20)
    draw.text((CAROUSEL_W // 2, CAROUSEL_H - 50), "Brad Wood • AI Operator", font=brand_font, fill=DIM_GRAY, anchor="mm")

    output_path = _resolve_output(output, "framework")
    img.save(output_path, "PNG")
    return output_path


# ---------------------------------------------------------------------------
# LinkedIn Carousel Generator
# ---------------------------------------------------------------------------

def gen_carousel(slides, output_dir):
    """Generate a LinkedIn carousel (PDF of slides).

    slides: list of dicts with 'title', 'body' (or 'points'), optional 'type'
    Types: title_slide, content_slide, stat_slide, closing_slide
    """
    output_dir = output_dir or os.path.join(IMAGE_DIR, "carousel-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    os.makedirs(output_dir, exist_ok=True)

    images = []
    for i, slide in enumerate(slides):
        slide_type = slide.get("type", "content_slide")

        if slide_type == "title_slide":
            img = _carousel_title_slide(slide)
        elif slide_type == "stat_slide":
            img = _carousel_stat_slide(slide)
        elif slide_type == "closing_slide":
            img = _carousel_closing_slide(slide)
        else:
            img = _carousel_content_slide(slide, i)

        path = os.path.join(output_dir, f"slide-{i:02d}.png")
        img.save(path, "PNG")
        images.append(img)

    # Also save as PDF for LinkedIn upload
    pdf_path = os.path.join(output_dir, "carousel.pdf")
    if images:
        images[0].save(pdf_path, "PDF", save_all=True, append_images=images[1:])

    return output_dir, pdf_path


def _carousel_title_slide(slide):
    """First slide — big title, hook."""
    img = Image.new("RGB", (CAROUSEL_W, CAROUSEL_H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Accent bar
    draw.rectangle([(0, 0), (CAROUSEL_W, 8)], fill=ACCENT_GREEN)

    # Title
    title_font = _load_font(52, bold=True, sans=True)
    title = slide.get("title", "")
    lines = _wrap_text(title, title_font, CAROUSEL_W - 120, draw)
    lh = _line_height(title_font)
    total_h = len(lines) * lh
    start_y = (CAROUSEL_H - total_h) // 2 - 60

    for i, line in enumerate(lines):
        draw.text((60, start_y + i * lh), line, font=title_font, fill=WHITE)

    # Subtitle
    if slide.get("body"):
        sub_font = _load_font(28, sans=True)
        sub_lines = _wrap_text(slide["body"], sub_font, CAROUSEL_W - 120, draw)
        sub_y = start_y + total_h + 40
        for line in sub_lines[:3]:
            draw.text((60, sub_y), line, font=sub_font, fill=GRAY)
            sub_y += _line_height(sub_font)

    # Swipe indicator
    swipe_font = _load_font(20, sans=True)
    draw.text((CAROUSEL_W // 2, CAROUSEL_H - 80), "Swipe \u2192", font=swipe_font, fill=ACCENT_GREEN, anchor="mm")

    # Branding
    brand_font = _load_font(20)
    draw.text((CAROUSEL_W // 2, CAROUSEL_H - 40), "Brad Wood • AI Operator", font=brand_font, fill=DIM_GRAY, anchor="mm")

    return img


def _carousel_content_slide(slide, index):
    """Content slide with numbered point."""
    img = Image.new("RGB", (CAROUSEL_W, CAROUSEL_H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Accent bar
    accent = [ACCENT_GREEN, ACCENT_TEAL, ACCENT_PURPLE, ACCENT_ORANGE][index % 4]
    draw.rectangle([(0, 0), (CAROUSEL_W, 6)], fill=accent)

    # Slide number
    num_font = _load_font(120, bold=True, sans=True)
    draw.text((60, 60), str(index), font=num_font, fill=accent + (40,) if len(accent) == 3 else accent)

    # Title
    title_font = _load_font(40, bold=True, sans=True)
    title = slide.get("title", "")
    tlines = _wrap_text(title, title_font, CAROUSEL_W - 120, draw)
    y = 200
    for line in tlines:
        draw.text((60, y), line, font=title_font, fill=WHITE)
        y += _line_height(title_font)

    # Body or points
    y += 30
    body_font = _load_font(26, sans=True)
    lh = _line_height(body_font)

    if slide.get("points"):
        for point in slide["points"]:
            if y + lh * 2 > CAROUSEL_H - 100:
                break
            draw.text((60, y), "\u2022", font=body_font, fill=accent)
            plines = _wrap_text(point, body_font, CAROUSEL_W - 160, draw)
            for pl in plines:
                draw.text((100, y), pl, font=body_font, fill=GRAY)
                y += lh
            y += 12
    elif slide.get("body"):
        blines = _wrap_text(slide["body"], body_font, CAROUSEL_W - 120, draw)
        for line in blines:
            if y + lh > CAROUSEL_H - 100:
                break
            draw.text((60, y), line, font=body_font, fill=GRAY)
            y += lh

    # Branding
    brand_font = _load_font(18)
    draw.text((CAROUSEL_W // 2, CAROUSEL_H - 40), "Brad Wood • AI Operator", font=brand_font, fill=DIM_GRAY, anchor="mm")

    return img


def _carousel_stat_slide(slide):
    """Big number stat slide."""
    img = Image.new("RGB", (CAROUSEL_W, CAROUSEL_H), BG_DARK)
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (CAROUSEL_W, 6)], fill=ACCENT_GREEN)

    # Big number
    stat_font = _load_font(140, bold=True, sans=True)
    stat = slide.get("stat", slide.get("title", ""))
    draw.text((CAROUSEL_W // 2, CAROUSEL_H // 2 - 80), stat, font=stat_font, fill=ACCENT_GREEN, anchor="mm")

    # Label
    label_font = _load_font(32, sans=True)
    label = slide.get("body", slide.get("label", ""))
    llines = _wrap_text(label, label_font, CAROUSEL_W - 120, draw)
    y = CAROUSEL_H // 2 + 40
    for line in llines:
        draw.text((CAROUSEL_W // 2, y), line, font=label_font, fill=GRAY, anchor="mm")
        y += _line_height(label_font)

    brand_font = _load_font(18)
    draw.text((CAROUSEL_W // 2, CAROUSEL_H - 40), "Brad Wood • AI Operator", font=brand_font, fill=DIM_GRAY, anchor="mm")

    return img


def _carousel_closing_slide(slide):
    """Final CTA/closing slide."""
    img = Image.new("RGB", (CAROUSEL_W, CAROUSEL_H), BG_DARK)
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (CAROUSEL_W, 6)], fill=ACCENT_PURPLE)

    # Closing text
    title_font = _load_font(44, bold=True, sans=True)
    title = slide.get("title", "That's the pattern.")
    tlines = _wrap_text(title, title_font, CAROUSEL_W - 120, draw)
    lh = _line_height(title_font)
    total_h = len(tlines) * lh
    start_y = (CAROUSEL_H - total_h) // 2 - 40

    for i, line in enumerate(tlines):
        draw.text((CAROUSEL_W // 2, start_y + i * lh), line, font=title_font, fill=WHITE, anchor="mm")

    # Follow prompt
    if slide.get("body"):
        sub_font = _load_font(26, sans=True)
        draw.text((CAROUSEL_W // 2, start_y + total_h + 50), slide["body"], font=sub_font, fill=ACCENT_PURPLE, anchor="mm")

    # Handle
    handle_font = _load_font(24, sans=True)
    draw.text((CAROUSEL_W // 2, CAROUSEL_H - 80), "@thebeedubya", font=handle_font, fill=ACCENT_GREEN, anchor="mm")

    brand_font = _load_font(18)
    draw.text((CAROUSEL_W // 2, CAROUSEL_H - 40), "Brad Wood • AI Operator", font=brand_font, fill=DIM_GRAY, anchor="mm")

    return img


# ---------------------------------------------------------------------------
# Nano Banana + PIL composite: generate background, overlay text
# ---------------------------------------------------------------------------

def gen_with_overlay(prompt, title, body, output):
    """Generate a Nano Banana image and overlay text with PIL."""
    # Generate base image
    base_path = generate_base_image(prompt, CAROUSEL_W, CAROUSEL_H)
    base = Image.open(base_path)

    # Dark overlay for text readability
    overlay = Image.new("RGBA", (CAROUSEL_W, CAROUSEL_H), (0, 0, 0, 140))
    base = base.convert("RGBA")
    composite = Image.alpha_composite(base, overlay)
    draw = ImageDraw.Draw(composite)

    # Title
    title_font = _load_font(44, bold=True, sans=True)
    tlines = _wrap_text(title, title_font, CAROUSEL_W - 120, draw)
    y = CAROUSEL_H // 2 - 100
    for line in tlines:
        draw.text((60, y), line, font=title_font, fill=WHITE)
        y += _line_height(title_font)

    # Body
    if body:
        body_font = _load_font(26, sans=True)
        y += 20
        blines = _wrap_text(body, body_font, CAROUSEL_W - 120, draw)
        for line in blines[:5]:
            draw.text((60, y), line, font=body_font, fill=(200, 200, 200))
            y += _line_height(body_font)

    # Branding
    brand_font = _load_font(20)
    draw.text((CAROUSEL_W // 2, CAROUSEL_H - 40), "Brad Wood • AI Operator", font=brand_font, fill=(150, 150, 150), anchor="mm")

    output_path = _resolve_output(output, "overlay")
    composite.convert("RGB").save(output_path, "PNG")

    # Clean up base
    os.unlink(base_path)

    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(description="Groundswell Image Generator — Nano Banana + PIL")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("generate", help="Generate image via Nano Banana (Gemini)")
    p.add_argument("--prompt", required=True)
    p.add_argument("--width", type=int, default=1080)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--output", default=None)

    p = sub.add_parser("carousel", help="Generate LinkedIn carousel (slides + PDF)")
    p.add_argument("--slides", required=True, help="JSON array of slide objects")
    p.add_argument("--output-dir", default=None)

    p = sub.add_parser("terminal", help="Terminal screenshot")
    p.add_argument("--text", required=True)
    p.add_argument("--output", default=None)

    p = sub.add_parser("quote", help="Quote card")
    p.add_argument("--text", required=True)
    p.add_argument("--attribution", default="— Brad Wood")
    p.add_argument("--output", default=None)

    p = sub.add_parser("framework", help="Framework breakdown slide")
    p.add_argument("--title", required=True)
    p.add_argument("--points", required=True, help="JSON array of point strings")
    p.add_argument("--output", default=None)

    p = sub.add_parser("overlay", help="Nano Banana image + text overlay")
    p.add_argument("--prompt", required=True, help="Image generation prompt")
    p.add_argument("--title", required=True)
    p.add_argument("--body", default="")
    p.add_argument("--output", default=None)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args.command == "generate":
        path = generate_base_image(args.prompt, args.width, args.height, args.output)
        emit({"ok": True, "image_path": path})
    elif args.command == "carousel":
        slides = json.loads(args.slides)
        out_dir, pdf_path = gen_carousel(slides, args.output_dir)
        emit({"ok": True, "output_dir": out_dir, "pdf_path": pdf_path, "slide_count": len(slides)})
    elif args.command == "terminal":
        path = gen_terminal(args.text, args.output)
        emit({"ok": True, "image_path": path})
    elif args.command == "quote":
        path = gen_quote(args.text, args.attribution, args.output)
        emit({"ok": True, "image_path": path})
    elif args.command == "framework":
        points = json.loads(args.points)
        path = gen_framework(args.title, points, args.output)
        emit({"ok": True, "image_path": path})
    elif args.command == "overlay":
        path = gen_with_overlay(args.prompt, args.title, args.body, args.output)
        emit({"ok": True, "image_path": path})
    else:
        fail(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
