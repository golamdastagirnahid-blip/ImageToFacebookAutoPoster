"""
Image post-processor for Facebook-optimal output.
- Resizes to FB-recommended dimensions (preserves aspect ratio)
- Adds subtle credit watermark OR full headline card overlay
- Auto-enhances faded historical scans
- Optimizes JPEG quality and progressive encoding
- Headline card mode: magazine-cover style poster with yellow-highlighted headline
"""
import os
import textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter


class ImageProcessor:
    # Facebook-optimal sizes
    FB_LANDSCAPE = (1200, 630)
    FB_SQUARE = (1080, 1080)
    FB_PORTRAIT = (1080, 1350)
    FB_MAX_WIDTH = 2048  # Above this FB compresses heavily

    def __init__(self, enable_watermark: bool = True,
                 watermark_text: str = "Public Domain Archives",
                 enable_enhance: bool = True,
                 enable_headline_card: bool = False,
                 brand_name: str = "Vintage Archives"):
        self.enable_watermark = enable_watermark
        self.watermark_text = watermark_text
        self.enable_enhance = enable_enhance
        self.enable_headline_card = enable_headline_card
        self.brand_name = brand_name

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

    def _load_font(self, size: int, bold: bool = True):
        """Try common system fonts; fall back to PIL default."""
        if bold:
            candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
        else:
            candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        return ImageFont.load_default()
    
    # ========================================================================
    # HEADLINE CARD MODE - Magazine-style poster with yellow-highlighted headline
    # ========================================================================
    def create_headline_card(self, image_path: str, headline: str,
                             subheadline: str = "", source_name: str = "",
                             output_path: str = None) -> str:
        """
        Compose a Facebook-optimal poster:
        - Top ~30%: textured off-white banner with bold headline on YELLOW highlight
        - Below: subheadline in dark gray (no highlight)
        - Bottom ~70%: the actual image
        - Right edge: vertical source/date text
        - Bottom-left: brand name
        
        Output: 1080x1350 portrait JPEG (Facebook-optimal)
        """
        try:
            CANVAS_W, CANVAS_H = 1080, 1350
            BANNER_H = 380  # Top banner height
            IMG_AREA_H = CANVAS_H - BANNER_H  # Bottom image area
            
            # Colors (matching the reference)
            BG_TEXTURED = (235, 232, 228)   # Off-white textured paper
            HIGHLIGHT_YELLOW = (255, 220, 0)
            TEXT_BLACK = (15, 15, 15)
            SUB_GRAY = (60, 60, 60)
            
            # Open and process source image
            src = Image.open(image_path)
            if src.mode != 'RGB':
                src = src.convert('RGB')
            try:
                from PIL import ImageOps
                src = ImageOps.exif_transpose(src)
            except Exception:
                pass
            
            # Auto-enhance the source image
            if self.enable_enhance:
                src = ImageEnhance.Contrast(src).enhance(1.08)
                src = ImageEnhance.Color(src).enhance(1.05)
                src = ImageEnhance.Sharpness(src).enhance(1.15)
            
            # Create canvas
            canvas = Image.new('RGB', (CANVAS_W, CANVAS_H), BG_TEXTURED)
            
            # Add subtle paper texture (very light noise)
            self._add_paper_texture(canvas, BANNER_H)
            
            # Fit source image into the bottom area (cover-style crop)
            img_fitted = self._fit_cover(src, CANVAS_W, IMG_AREA_H)
            canvas.paste(img_fitted, (0, BANNER_H))
            
            # Draw headline with yellow highlight
            draw = ImageDraw.Draw(canvas)
            self._draw_headline_block(draw, headline, subheadline,
                                       canvas_w=CANVAS_W, banner_h=BANNER_H,
                                       highlight=HIGHLIGHT_YELLOW,
                                       text_color=TEXT_BLACK,
                                       sub_color=SUB_GRAY)
            
            # Brand name (bottom-left)
            self._draw_brand(draw, CANVAS_W, CANVAS_H, self.brand_name, TEXT_BLACK)
            
            # Vertical source/date text (right edge)
            if source_name:
                self._draw_vertical_source(canvas, source_name,
                                            BANNER_H, CANVAS_H, CANVAS_W)
            
            # Save
            if output_path is None:
                output_path = image_path
            canvas.save(output_path, 'JPEG', quality=90, optimize=True, progressive=True)
            print(f"🎨 Headline card created: {CANVAS_W}x{CANVAS_H}")
            return output_path
        except Exception as e:
            import traceback
            print(f"Headline card failed (using basic processing): {e}")
            traceback.print_exc()
            return self.process(image_path, source_name=source_name)
    
    def _fit_cover(self, img: Image.Image, target_w: int, target_h: int) -> Image.Image:
        """Resize and center-crop image to fill target dimensions (cover style)."""
        sw, sh = img.size
        scale = max(target_w / sw, target_h / sh)
        new_w, new_h = int(sw * scale), int(sh * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        # Center crop
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return img.crop((left, top, left + target_w, top + target_h))
    
    def _add_paper_texture(self, canvas: Image.Image, banner_h: int):
        """Subtle paper-like noise on the top banner area."""
        try:
            import random
            pixels = canvas.load()
            w = canvas.width
            for y in range(0, banner_h, 2):
                for x in range(0, w, 2):
                    if random.random() < 0.15:
                        r, g, b = pixels[x, y]
                        delta = random.randint(-12, 8)
                        pixels[x, y] = (
                            max(0, min(255, r + delta)),
                            max(0, min(255, g + delta)),
                            max(0, min(255, b + delta)),
                        )
        except Exception:
            pass
    
    def _wrap_text(self, text: str, font, max_width: int, draw) -> list:
        """Word-wrap text to fit max_width pixels. Returns list of lines."""
        words = text.split()
        lines = []
        current = []
        for word in words:
            test = ' '.join(current + [word])
            try:
                bbox = draw.textbbox((0, 0), test, font=font)
                tw = bbox[2] - bbox[0]
            except AttributeError:
                tw, _ = draw.textsize(test, font=font)
            if tw <= max_width or not current:
                current.append(word)
            else:
                lines.append(' '.join(current))
                current = [word]
        if current:
            lines.append(' '.join(current))
        return lines
    
    def _draw_headline_block(self, draw, headline: str, subheadline: str,
                              canvas_w: int, banner_h: int,
                              highlight, text_color, sub_color):
        """Draw the headline (with yellow highlight) and subheadline."""
        margin = 40
        max_text_w = canvas_w - 2 * margin
        
        # Auto-size headline font (target: fits in ~2 lines)
        headline_size = 64
        font_h = self._load_font(headline_size, bold=True)
        lines = self._wrap_text(headline, font_h, max_text_w, draw)
        # Shrink if too many lines
        while len(lines) > 3 and headline_size > 40:
            headline_size -= 4
            font_h = self._load_font(headline_size, bold=True)
            lines = self._wrap_text(headline, font_h, max_text_w, draw)
        
        # Subheadline font
        sub_size = max(28, int(headline_size * 0.55))
        font_s = self._load_font(sub_size, bold=True)
        sub_lines = self._wrap_text(subheadline, font_s, max_text_w, draw) if subheadline else []
        
        # Calculate total text height
        line_spacing = int(headline_size * 0.18)
        line_h = headline_size + line_spacing
        sub_line_h = sub_size + int(sub_size * 0.2)
        total_h = len(lines) * line_h
        if sub_lines:
            total_h += int(headline_size * 0.4) + len(sub_lines) * sub_line_h
        
        # Vertically center within banner
        y = max(margin, (banner_h - total_h) // 2)
        
        # Draw headline lines with yellow highlight
        highlight_pad_x = 14
        highlight_pad_y = 6
        for line in lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=font_h)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                # Adjust for font ascender
                ascent = -bbox[1]
            except AttributeError:
                tw, th = draw.textsize(line, font=font_h)
                ascent = 0
            
            x = margin
            # Yellow highlight rectangle
            draw.rectangle(
                (x - highlight_pad_x, y - highlight_pad_y + ascent // 4,
                 x + tw + highlight_pad_x, y + th + highlight_pad_y + ascent // 4),
                fill=highlight
            )
            draw.text((x, y), line, font=font_h, fill=text_color)
            y += line_h
        
        # Subheadline (no highlight)
        if sub_lines:
            y += int(headline_size * 0.25)
            for line in sub_lines:
                draw.text((margin, y), line, font=font_s, fill=sub_color)
                y += sub_line_h
    
    def _draw_brand(self, draw, canvas_w, canvas_h, brand_name, color):
        """Draw brand name in bottom-left with semi-transparent backdrop."""
        try:
            font = self._load_font(36, bold=True)
            margin = 40
            text = brand_name
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
            except AttributeError:
                tw, th = draw.textsize(text, font=font)
            
            x = margin
            y = canvas_h - margin - th - 10
            
            # White backdrop strip with rounded corners
            pad = 14
            draw.rectangle(
                (x - pad, y - pad, x + tw + pad, y + th + pad),
                fill=(255, 255, 255, 230)
            )
            draw.text((x, y), text, font=font, fill=color)
        except Exception as e:
            print(f"   Brand draw error: {e}")
    
    def _draw_vertical_source(self, canvas: Image.Image, source_name: str,
                               banner_h: int, canvas_h: int, canvas_w: int):
        """Draw vertical source/date text on the right edge of the image area."""
        try:
            font = self._load_font(20, bold=False)
            date_str = datetime.now().strftime("%d %b %Y")
            text = f"Source: {source_name[:40]}  |  {date_str}  |  Public Domain"
            
            # Render text on a transparent strip, then rotate 90° clockwise (270 = read top-down)
            tmp_w = canvas_h - banner_h - 80  # Length of text strip
            tmp_h = 32
            strip = Image.new('RGBA', (tmp_w, tmp_h), (0, 0, 0, 0))
            sd = ImageDraw.Draw(strip)
            sd.text((0, 4), text, font=font, fill=(255, 255, 255, 230))
            
            # Rotate so it reads top-to-bottom on the right edge
            rotated = strip.rotate(270, expand=True)
            rw, rh = rotated.size
            
            # Position on right edge of image area
            x = canvas_w - rh - 12
            y = banner_h + 40
            canvas.paste(rotated, (x, y), rotated)
        except Exception as e:
            print(f"   Vertical source draw error: {e}")
