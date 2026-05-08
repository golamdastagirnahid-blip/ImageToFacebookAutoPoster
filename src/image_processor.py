"""
Image post-processor for Facebook-optimal output.
- Resizes to FB-recommended dimensions (preserves aspect ratio)
- Adds subtle credit watermark
- Auto-enhances faded historical scans
- Optimizes JPEG quality and progressive encoding
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter


class ImageProcessor:
    # Facebook-optimal sizes
    FB_LANDSCAPE = (1200, 630)
    FB_SQUARE = (1080, 1080)
    FB_PORTRAIT = (1080, 1350)
    FB_MAX_WIDTH = 2048  # Above this FB compresses heavily

    def __init__(self, enable_watermark: bool = True,
                 watermark_text: str = "Public Domain Archives",
                 enable_enhance: bool = True):
        self.enable_watermark = enable_watermark
        self.watermark_text = watermark_text
        self.enable_enhance = enable_enhance

    def process(self, image_path: str, source_name: str = None) -> str:
        """
        Process image for Facebook posting. Returns path to processed image.
        Modifies in-place if successful, returns original path on failure.
        """
        try:
            img = Image.open(image_path)

            # Convert to RGB (drops alpha, fixes palette modes)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Step 1: Auto-orient based on EXIF
            try:
                from PIL import ImageOps
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            # Step 2: Smart resize to FB-optimal
            img = self._smart_resize(img)

            # Step 3: Auto-enhance for old scans
            if self.enable_enhance:
                img = self._auto_enhance(img)

            # Step 4: Add watermark
            if self.enable_watermark:
                wm_text = source_name or self.watermark_text
                img = self._add_watermark(img, wm_text)

            # Step 5: Save with optimization
            output_path = image_path  # Overwrite
            img.save(output_path, 'JPEG', quality=88, optimize=True, progressive=True)
            
            print(f"🎨 Processed: {img.size[0]}x{img.size[1]}, optimized JPEG")
            return output_path
        except Exception as e:
            print(f"Image processing error (using original): {e}")
            return image_path

    def _smart_resize(self, img: Image.Image) -> Image.Image:
        """Resize to FB-optimal while preserving aspect ratio. Never upscales."""
        w, h = img.size
        ratio = w / h

        # Determine target based on aspect ratio
        if ratio > 1.4:  # Wide/landscape
            target_w = min(w, self.FB_LANDSCAPE[0] * 1.5)  # 1800 max for crisp landscape
        elif ratio < 0.85:  # Portrait
            target_w = min(w, self.FB_PORTRAIT[0])
        else:  # Roughly square
            target_w = min(w, self.FB_SQUARE[0])

        # Cap at FB_MAX_WIDTH
        target_w = min(target_w, self.FB_MAX_WIDTH)

        if target_w < w:
            scale = target_w / w
            new_size = (int(target_w), int(h * scale))
            img = img.resize(new_size, Image.LANCZOS)
            print(f"   Resized: {w}x{h} → {new_size[0]}x{new_size[1]}")

        return img

    def _auto_enhance(self, img: Image.Image) -> Image.Image:
        """Subtle enhancement for old/faded scans."""
        try:
            # Slight contrast boost (1.0 = unchanged, >1 = more contrast)
            img = ImageEnhance.Contrast(img).enhance(1.08)
            # Slight color saturation (helps faded color scans)
            img = ImageEnhance.Color(img).enhance(1.05)
            # Subtle sharpness (most archive scans are slightly soft)
            img = ImageEnhance.Sharpness(img).enhance(1.15)
        except Exception as e:
            print(f"   Enhancement skipped: {e}")
        return img

    def _add_watermark(self, img: Image.Image, text: str) -> Image.Image:
        """Add subtle bottom-right watermark with credit."""
        try:
            w, h = img.size
            # Watermark size: ~2% of image height, min 14px max 32px
            font_size = max(14, min(32, int(h * 0.022)))

            # Try to load a font; fall back to default
            font = self._load_font(font_size)

            draw = ImageDraw.Draw(img, 'RGBA')

            # Build watermark text
            wm = f"📜 {text}"
            
            # Measure text
            try:
                bbox = draw.textbbox((0, 0), wm, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
            except AttributeError:
                # Older Pillow
                text_w, text_h = draw.textsize(wm, font=font)

            padding = max(8, int(font_size * 0.4))
            x = w - text_w - padding * 2
            y = h - text_h - padding * 2

            # Semi-transparent dark background bar
            bg_box = (x - padding, y - padding,
                      x + text_w + padding, y + text_h + padding)
            draw.rectangle(bg_box, fill=(0, 0, 0, 140))

            # White text
            draw.text((x, y), wm, font=font, fill=(255, 255, 255, 230))
        except Exception as e:
            print(f"   Watermark skipped: {e}")
        return img

    def _load_font(self, size: int):
        """Try common system fonts; fall back to PIL default."""
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux/GitHub Actions
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",  # Windows
            "C:/Windows/Fonts/arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        return ImageFont.load_default()
