import os
import hashlib
import secrets
from datetime import datetime
from typing import Tuple
from PIL import Image, ImageDraw, ImageFont
import qrcode
from config import settings


def generate_certificate(
    user_name: str,
    assessment_title: str,
    score: float,
    submission_id: int,
    cert_dir: str = None
) -> Tuple[str, str]:
    """
    Generate a beautiful certificate PNG with QR code.
    Returns: (cert_filename, qr_hash)
    """
    cert_dir = cert_dir or settings.CERT_DIR
    os.makedirs(cert_dir, exist_ok=True)

    # Generate unique hash for verification
    qr_hash = hashlib.sha256(
        f"{user_name}{assessment_title}{submission_id}{secrets.token_hex(8)}".encode()
    ).hexdigest()[:32]

    # Certificate dimensions (A4 landscape-ish)
    W, H = 1200, 850
    img = Image.new("RGB", (W, H), color=(15, 12, 41))  # Deep dark background

    draw = ImageDraw.Draw(img)

    # ─── Gradient-style border ─────────────────────────────────────────────────
    for i in range(8):
        draw.rectangle(
            [i, i, W - i - 1, H - i - 1],
            outline=(99 + i * 10, 102 + i * 5, 241 - i * 10)
        )

    # ─── Decorative corners (drawn shapes, not Unicode) ────────────────────────
    corner_size = 60
    for cx, cy in [(30, 30), (W - 30 - corner_size, 30), (30, H - 30 - corner_size), (W - 30 - corner_size, H - 30 - corner_size)]:
        draw.rectangle([cx, cy, cx + corner_size, cy + corner_size], outline=(139, 92, 246), width=3)

    # ─── Star decorations (drawn as diamond shapes instead of Unicode) ─────────
    def draw_diamond(draw, x, y, size=10, fill=(139, 92, 246)):
        points = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
        draw.polygon(points, fill=fill)

    for x, y in [(150, 100), (1050, 100), (100, 750), (1100, 750)]:
        draw_diamond(draw, x, y, size=8, fill=(139, 92, 246))

    # Small dot accents
    for x, y in [(180, 120), (1020, 120), (130, 730), (1070, 730)]:
        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(99, 102, 241))

    # ─── Load fonts (fallback chain) ──────────────────────────────────────────
    def try_font(size):
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSDisplay.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for fp in font_paths:
            try:
                return ImageFont.truetype(fp, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    font_large = try_font(64)
    font_medium = try_font(36)
    font_small = try_font(24)
    font_tiny = try_font(18)

    # ─── Logo/Title (ASCII only) ───────────────────────────────────────────────
    draw.text((W // 2, 80), "KAUSHALYAAI", font=font_medium, fill=(0, 86, 210), anchor="mm")
    draw.text((W // 2, 130), "CERTIFICATE OF ACHIEVEMENT", font=font_small, fill=(148, 163, 184), anchor="mm")

    # Separator line
    draw.line([(100, 165), (1100, 165)], fill=(99, 102, 241), width=2)

    # ─── Main Content ──────────────────────────────────────────────────────────
    draw.text((W // 2, 240), "This is to certify that", font=font_small, fill=(148, 163, 184), anchor="mm")
    draw.text((W // 2, 320), user_name, font=font_large, fill=(255, 255, 255), anchor="mm")

    draw.line([(300, 360), (900, 360)], fill=(99, 102, 241), width=1)

    draw.text((W // 2, 410), "has successfully demonstrated mastery in", font=font_small, fill=(148, 163, 184), anchor="mm")

    # Assessment title (wrap if long)
    title_display = assessment_title if len(assessment_title) <= 45 else assessment_title[:42] + "..."
    draw.text((W // 2, 480), title_display, font=font_medium, fill=(99, 102, 241), anchor="mm")

    # Score badge
    score_color = (16, 185, 129) if score >= 70 else (245, 158, 11) if score >= 50 else (239, 68, 68)
    draw.ellipse([(W // 2 - 70, 540), (W // 2 + 70, 680)], fill=(30, 27, 75))
    draw.ellipse([(W // 2 - 65, 545), (W // 2 + 65, 675)], outline=score_color, width=3)
    draw.text((W // 2, 590), f"{score:.0f}%", font=font_medium, fill=score_color, anchor="mm")
    draw.text((W // 2, 645), "Score", font=font_tiny, fill=(148, 163, 184), anchor="mm")

    # Date
    issue_date = datetime.utcnow().strftime("%B %d, %Y")
    draw.text((250, 760), f"Issued: {issue_date}", font=font_tiny, fill=(148, 163, 184), anchor="mm")
    draw.text((W // 2, 760), f"ID: {qr_hash[:16].upper()}", font=font_tiny, fill=(99, 102, 241), anchor="mm")

    # ─── QR Code ──────────────────────────────────────────────────────────────
    verify_url = f"{settings.BACKEND_URL}/api/certificates/verify/{qr_hash}"
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="white", back_color=(15, 12, 41))
    qr_img = qr_img.resize((120, 120))
    img.paste(qr_img, (1030, 700))
    draw.text((1090, 825), "Verify", font=font_tiny, fill=(148, 163, 184), anchor="mm")

    # ─── Save ─────────────────────────────────────────────────────────────────
    cert_filename = f"cert_{qr_hash}.png"
    cert_path = os.path.join(cert_dir, cert_filename)
    img.save(cert_path, "PNG", quality=95)

    return cert_filename, qr_hash
