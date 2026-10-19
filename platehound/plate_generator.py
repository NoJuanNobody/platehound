"""
PlateHound Synthetic Florida License Plate Generator.
Generates photorealistic synthetic Florida license plate images matching standard
Sunshine State styling (gradient background, MYFLORIDA.COM header, citrus emblem,
embossed dark-green characters, registration decals, and SUNSHINE STATE footer).
Embeds metadata into PNG chunks to enable high-accuracy ALPR testing.
"""

import os
import json
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

SAMPLE_PLATES = [
    "76BCDE",
    "ABC123",
    "XYZ789",
    "FLFAST",
    "SUNSHN",
    "MIA305",
    "GATOR1",
    "305EV1",
]


def _get_font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    """Load system font with cross-platform fallbacks."""
    font_candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for candidate in font_candidates:
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def draw_florida_citrus_emblem(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    """Draw the iconic Florida citrus (two oranges with leaves) at center (cx, cy)."""
    # Leaves on top
    draw.polygon([(cx - 5, cy - 24), (cx - 22, cy - 38), (cx - 4, cy - 32)], fill=(34, 139, 34))
    draw.polygon([(cx + 5, cy - 24), (cx + 24, cy - 36), (cx + 4, cy - 30)], fill=(46, 160, 50))
    # Stem
    draw.ellipse([cx - 4, cy - 28, cx + 4, cy - 22], fill=(70, 45, 20))
    # Left orange
    draw.ellipse([cx - 28, cy - 18, cx + 2, cy + 16], fill=(255, 130, 0), outline=(210, 90, 0), width=1)
    # Right orange
    draw.ellipse([cx - 2, cy - 14, cx + 28, cy + 20], fill=(255, 148, 0), outline=(220, 100, 0), width=1)


def generate_plate_image(
    plate_text: str,
    output_path: Optional[str] = None,
    width: int = 600,
    height: int = 340,
    include_bumper: bool = True
) -> str:
    """
    Generates a synthetic Florida license plate image for ALPR testing.
    
    Args:
        plate_text: The license plate string (e.g. '76BCDE', 'FLFAST')
        output_path: Target path for the PNG file. If None, saves to samples/plates/<plate>.png.
        width: Frame width in pixels (default 600).
        height: Frame height in pixels (default 340).
        include_bumper: If True, renders dark vehicle bumper mounting context.
        
    Returns:
        The absolute path to the generated image file.
    """
    clean_text = plate_text.strip().upper()
    if output_path is None:
        os.makedirs("samples/plates", exist_ok=True)
        output_path = os.path.join("samples", "plates", f"{clean_text}.png")
    
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Frame background
    bg_color = (28, 30, 34) if include_bumper else (255, 255, 255)
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Plate dimensions and bounding box
    if include_bumper:
        px, py, pw, ph = 40, 40, 520, 260
        # Subtle bumper lines
        draw.line([(0, 15), (width, 15)], fill=(20, 22, 25), width=2)
        draw.line([(0, height - 15), (width, height - 15)], fill=(20, 22, 25), width=2)
    else:
        px, py, pw, ph = 0, 0, width, height

    bbox = [px, py, pw, ph]

    # Plate body gradient (off-white / pearl)
    plate_img = Image.new("RGB", (pw, ph), color=(248, 250, 246))
    pdraw = ImageDraw.Draw(plate_img)
    for y in range(ph):
        ratio = y / ph
        r = int(248 * (1 - ratio * 0.04))
        g = int(250 * (1 - ratio * 0.03))
        b = int(246 * (1 - ratio * 0.05))
        pdraw.line([(0, y), (pw, y)], fill=(r, g, b))

    # Mask plate with rounded corners
    radius = 18 if include_bumper else 12
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], radius=radius, fill=255)
    img.paste(plate_img, (px, py), mask)

    # Plate borders (dark green Florida outer trim + inner embossed bevel)
    fl_green = (15, 77, 42)
    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=radius, outline=fl_green, width=4)
    draw.rounded_rectangle([px + 3, py + 3, px + pw - 3, py + ph - 3], radius=radius - 3, outline=(220, 228, 218), width=1)

    # 4 bolt holes with metallic washers
    hole_offsets = [
        (px + 42, py + 35),
        (px + pw - 42, py + 35),
        (px + 42, py + ph - 35),
        (px + pw - 42, py + ph - 35)
    ]
    for hx, hy in hole_offsets:
        draw.ellipse([hx - 9, hy - 9, hx + 9, hy + 9], fill=(205, 210, 205), outline=(130, 135, 130), width=1)
        draw.ellipse([hx - 5, hy - 5, hx + 5, hy + 5], fill=(38, 40, 42))

    # Decals: Registration sticker (top-right) and County (top-left)
    # Registration decal: Gold/yellow with dark border
    draw.rectangle([px + pw - 75, py + 16, px + pw - 20, py + 52], fill=(255, 198, 30), outline=(120, 90, 10), width=1)
    # County banner: light tint
    draw.rectangle([px + 20, py + 16, px + 75, py + 52], fill=(240, 242, 238), outline=(210, 215, 205), width=1)

    # Fonts
    font_head = _get_font(24, bold=True)
    font_sub = _get_font(11, bold=True)
    font_foot = _get_font(21, bold=True)
    
    # Scale character font based on plate length
    char_size = 76 if len(clean_text) <= 6 else 68
    font_char = _get_font(char_size, bold=True)

    # Decal text
    draw.text((px + pw - 48, py + 34), "12-26", fill=(20, 20, 20), font=font_sub, anchor="mm")
    draw.text((px + 48, py + 34), "DADE", fill=fl_green, font=font_sub, anchor="mm")

    # Header: MYFLORIDA.COM
    draw.text((px + pw // 2, py + 34), "MYFLORIDA.COM", fill=fl_green, font=font_head, anchor="mm")

    # Center Citrus Graphic (Iconic Florida Oranges)
    cx, cy = px + pw // 2, py + ph // 2
    draw_florida_citrus_emblem(draw, cx, cy)

    # Plate Characters: Stamped metal relief effect (shadow, highlight, face)
    char_color = (12, 72, 38)
    shadow_color = (6, 40, 20)
    highlight_color = (45, 115, 75)

    cy_text = py + 128
    # 1px offset shadow and highlight for embossed depth
    draw.text((cx + 1, cy_text + 1), clean_text, fill=shadow_color, font=font_char, anchor="mm")
    draw.text((cx - 1, cy_text - 1), clean_text, fill=highlight_color, font=font_char, anchor="mm")
    draw.text((cx, cy_text), clean_text, fill=char_color, font=font_char, anchor="mm")

    # Footer: SUNSHINE STATE
    draw.text((px + pw // 2, py + ph - 30), "SUNSHINE STATE", fill=fl_green, font=font_foot, anchor="mm")

    # Embed PNG Metadata
    meta = PngInfo()
    meta.add_text("Plate", clean_text)
    meta.add_text("State", "FL")
    meta.add_text("BBox", json.dumps(bbox))
    meta.add_text("Header", "MYFLORIDA.COM")
    meta.add_text("Footer", "SUNSHINE STATE")
    meta.add_text("Generator", "PlateHound Florida ALPR Synthesizer")

    img.save(output_path, "PNG", pnginfo=meta)
    return os.path.abspath(output_path)


def generate_sample_plates(output_dir: str = "samples/plates") -> List[str]:
    """
    Generates synthetic Florida license plate images for all default sample plates.
    
    Args:
        output_dir: Target directory path (default 'samples/plates')
        
    Returns:
        List of generated image paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    generated_paths = []
    for plate in SAMPLE_PLATES:
        dest_path = os.path.join(output_dir, f"{plate}.png")
        saved = generate_plate_image(plate, dest_path)
        generated_paths.append(saved)
    return generated_paths


if __name__ == "__main__":
    import sys
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "samples/plates"
    print(f"🐾 Generating synthetic Florida plates into '{out_dir}'...")
    paths = generate_sample_plates(out_dir)
    print(f"✅ Generated {len(paths)} sample plates:")
    for p in paths:
        print(f"   - {p}")
