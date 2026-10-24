"""Generate Realistic Test Payment Screenshots for CleanCheck

Creates 4 distinct sample images using Pillow:
1. sample_genuine.png: Authentic-looking UPI screenshot matching a seeded ledger entry.
2. sample_tampered.png: Tampered screenshot (altered amount ₹7,500 vs ledger ₹750, editing tool tag, spliced patch).
3. sample_duplicate.png: Duplicate copy of sample_genuine for testing perceptual hash collision.
4. sample_non_payment.png: Non-payment storefront / store product photo with no UPI reference.
"""

import sys
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
import numpy as np

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import SAMPLES_DIR


def get_default_font(size: int = 16):
    """Loads a clean system font or Pillow default."""
    try:
        # Common Windows fonts
        for font_name in ["segoeui.ttf", "arial.ttf", "calibri.ttf"]:
            try:
                return ImageFont.truetype(font_name, size)
            except Exception:
                continue
    except Exception:
        pass
    return ImageFont.load_default()


def generate_genuine_sample() -> Path:
    """Generates a genuine-looking Google Pay / UPI receipt screenshot."""
    w, h = 420, 780
    img = Image.new("RGB", (w, h), color=(248, 249, 250))
    draw = ImageDraw.Draw(img)

    # Top App Bar (Google Pay styling)
    draw.rectangle([(0, 0), (w, 65)], fill=(255, 255, 255))
    font_title = get_default_font(20)
    font_sub = get_default_font(13)
    font_bold = get_default_font(15)
    font_amt = get_default_font(34)
    font_small = get_default_font(12)

    draw.text((25, 22), "Google Pay", fill=(60, 64, 67), font=font_title)

    # Success Badge
    center_x = w // 2
    draw.ellipse([(center_x - 34, 100), (center_x + 34, 168)], fill=(30, 142, 62))
    # Draw checkmark
    draw.line([(center_x - 14, 134), (center_x - 4, 146)], fill=(255, 255, 255), width=4)
    draw.line([(center_x - 4, 146), (center_x + 16, 120)], fill=(255, 255, 255), width=4)

    draw.text((center_x - 70, 185), "Payment Successful", fill=(30, 142, 62), font=font_bold)

    # Amount
    draw.text((center_x - 65, 225), "₹ 750.00", fill=(32, 33, 36), font=font_amt)

    # Receiver card
    draw.rectangle([(25, 290), (w - 25, 420)], fill=(255, 255, 255), outline=(222, 226, 230), width=1)
    draw.text((45, 305), "Paid to", fill=(128, 134, 139), font=font_sub)
    draw.text((45, 328), "Shop Easy", fill=(32, 33, 36), font=font_bold)
    draw.text((45, 350), "shopeasy@hdfcbank", fill=(95, 99, 104), font=font_sub)
    draw.text((45, 380), "From: Rohan Sharma (rohan.sharma@okaxis)", fill=(95, 99, 104), font=font_sub)

    # Transaction Details Card
    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
    draw.rectangle([(25, 435), (w - 25, 680)], fill=(255, 255, 255), outline=(222, 226, 230), width=1)
    draw.text((45, 455), "Transaction Details", fill=(32, 33, 36), font=font_bold)
    draw.line([(45, 485), (w - 45, 485)], fill=(238, 238, 238), width=1)

    details = [
        ("UPI Ref ID", "428901928374"),
        ("Date & Time", now_str),
        ("Payment Mode", "UPI - HDFC Bank A/c **4921"),
        ("Google Transaction ID", "CICAgOCz_728Xw"),
        ("Status", "COMPLETED"),
    ]

    y_pos = 505
    for label, val in details:
        draw.text((45, y_pos), label, fill=(128, 134, 139), font=font_small)
        draw.text((45, y_pos + 18), val, fill=(32, 33, 36), font=font_bold if label == "UPI Ref ID" else font_sub)
        y_pos += 44

    # Embed full raw text in PNG info chunk for robust test portability
    raw_text = (
        f"Google Pay\nPayment Successful\n₹ 750.00\nPaid to Shop Easy\nshopeasy@hdfcbank\n"
        f"From: Rohan Sharma (rohan.sharma@okaxis)\nTransaction Details\n"
        f"UPI Ref ID: 428901928374\nDate: {now_str}\nStatus: SUCCESS COMPLETED\n"
        f"Google Transaction ID: CICAgOCz_728Xw"
    )
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("CleanCheck_Text", raw_text)

    out_file = SAMPLES_DIR / "sample_genuine.png"
    img.save(out_file, "PNG", pnginfo=pnginfo)
    print(f"Generated Genuine Sample: {out_file}")
    return out_file


def generate_tampered_sample() -> Path:
    """Generates a tampered screenshot: altered amount ₹7,500.00, Photoshop tag, spliced noise patch."""
    w, h = 420, 780
    img = Image.new("RGB", (w, h), color=(248, 249, 250))
    draw = ImageDraw.Draw(img)

    font_title = get_default_font(20)
    font_sub = get_default_font(13)
    font_bold = get_default_font(15)
    font_tampered_amt = get_default_font(36)
    font_small = get_default_font(12)

    # Top Bar
    draw.rectangle([(0, 0), (w, 65)], fill=(255, 255, 255))
    draw.text((25, 22), "Google Pay", fill=(60, 64, 67), font=font_title)

    # Success Badge
    center_x = w // 2
    draw.ellipse([(center_x - 34, 100), (center_x + 34, 168)], fill=(30, 142, 62))
    draw.line([(center_x - 14, 134), (center_x - 4, 146)], fill=(255, 255, 255), width=4)
    draw.line([(center_x - 4, 146), (center_x + 16, 120)], fill=(255, 255, 255), width=4)
    draw.text((center_x - 70, 185), "Payment Successful", fill=(30, 142, 62), font=font_bold)

    # TAMPERED AMOUNT PATCH:
    # A spliced white rectangle patch with slight border/color variance simulating copy-paste
    patch_box = [(center_x - 110, 220), (center_x + 110, 275)]
    draw.rectangle(patch_box, fill=(254, 254, 252))  # Mismatched background shade
    # Add localized synthetic noise inside the patch
    noise = np.random.randint(-15, 15, (55, 220, 3), dtype=np.int16)
    patch_crop = np.array(img.crop((patch_box[0][0], patch_box[0][1], patch_box[1][0], patch_box[1][1])), dtype=np.int16)
    noisy_patch = np.clip(patch_crop + noise, 0, 255).astype(np.uint8)
    patch_img = Image.fromarray(noisy_patch)
    img.paste(patch_img, (patch_box[0][0], patch_box[0][1]))

    # Re-draw text over patch with altered amount ₹7,500.00
    draw = ImageDraw.Draw(img)
    draw.text((center_x - 85, 225), "₹ 7,500.00", fill=(10, 10, 10), font=font_tampered_amt)

    # Receiver card
    draw.rectangle([(25, 290), (w - 25, 420)], fill=(255, 255, 255), outline=(222, 226, 230), width=1)
    draw.text((45, 305), "Paid to", fill=(128, 134, 139), font=font_sub)
    draw.text((45, 328), "Shop Easy", fill=(32, 33, 36), font=font_bold)
    draw.text((45, 350), "shopeasy@hdfcbank", fill=(95, 99, 104), font=font_sub)
    draw.text((45, 380), "From: Rohan Sharma (rohan.sharma@okaxis)", fill=(95, 99, 104), font=font_sub)

    # Details Card (still references UTR 428901928374 which only had ₹750 in ledger!)
    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
    draw.rectangle([(25, 435), (w - 25, 680)], fill=(255, 255, 255), outline=(222, 226, 230), width=1)
    draw.text((45, 455), "Transaction Details", fill=(32, 33, 36), font=font_bold)
    draw.line([(45, 485), (w - 45, 485)], fill=(238, 238, 238), width=1)

    details = [
        ("UPI Ref ID", "428901928374"),
        ("Date & Time", now_str),
        ("Payment Mode", "UPI - HDFC Bank A/c **4921"),
        ("Google Transaction ID", "CICAgOCz_728Xw"),
        ("Status", "COMPLETED"),
    ]

    y_pos = 505
    for label, val in details:
        draw.text((45, y_pos), label, fill=(128, 134, 139), font=font_small)
        draw.text((45, y_pos + 18), val, fill=(32, 33, 36), font=font_bold if label == "UPI Ref ID" else font_sub)
        y_pos += 44

    # Explicitly add Photoshop tag in metadata for forensic metadata check
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("Software", "Adobe Photoshop 2024 (Windows)")
    raw_text = (
        f"Google Pay\nPayment Successful\n₹ 7,500.00\nPaid to Shop Easy\nshopeasy@hdfcbank\n"
        f"From: Rohan Sharma (rohan.sharma@okaxis)\nTransaction Details\n"
        f"UPI Ref ID: 428901928374\nDate: {now_str}\nStatus: SUCCESS COMPLETED\n"
        f"Google Transaction ID: CICAgOCz_728Xw"
    )
    pnginfo.add_text("CleanCheck_Text", raw_text)

    out_file = SAMPLES_DIR / "sample_tampered.png"
    img.save(out_file, "PNG", pnginfo=pnginfo)
    print(f"Generated Tampered Sample: {out_file}")
    return out_file


def generate_duplicate_sample(genuine_path: Path) -> Path:
    """Generates a duplicate copy for testing perceptual hash collision."""
    img = Image.open(genuine_path)
    out_file = SAMPLES_DIR / "sample_duplicate.png"
    # Save copy preserving content & hash
    img.save(out_file, "PNG")
    print(f"Generated Duplicate Sample: {out_file}")
    return out_file


def generate_non_payment_sample() -> Path:
    """Generates a non-payment image (e.g. store promotion / storefront banner)."""
    w, h = 420, 600
    img = Image.new("RGB", (w, h), color=(255, 236, 179))
    draw = ImageDraw.Draw(img)

    font_title = get_default_font(28)
    font_body = get_default_font(16)

    # Decorative header
    draw.rectangle([(0, 0), (w, 180)], fill=(255, 179, 0))
    draw.text((40, 60), "Shop Easy Supermarket", fill=(40, 40, 40), font=font_title)
    draw.text((40, 110), "Fresh Fruits & Daily Essentials", fill=(60, 60, 60), font=font_body)

    # Body
    draw.rectangle([(30, 210), (w - 30, 540)], fill=(255, 255, 255), outline=(220, 220, 220))
    draw.text((50, 240), "Weekend Festival Offer!", fill=(230, 81, 0), font=get_default_font(22))
    draw.text((50, 290), "• Flat 20% discount on organic pulses", fill=(60, 60, 60), font=font_body)
    draw.text((50, 330), "• Buy 1 Get 1 Free on all bakery items", fill=(60, 60, 60), font=font_body)
    draw.text((50, 370), "• Fresh apples ₹120/kg", fill=(60, 60, 60), font=font_body)
    draw.text((50, 430), "Store Hours: 8:00 AM - 10:00 PM", fill=(100, 100, 100), font=font_body)
    draw.text((50, 470), "Helpline: +91 98765 43210", fill=(100, 100, 100), font=font_body)

    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("CleanCheck_Text", "Shop Easy Supermarket\nWeekend Festival Offer\nStore Hours: 8:00 AM - 10:00 PM\nHelpline: +91 98765 43210")

    out_file = SAMPLES_DIR / "sample_non_payment.png"
    img.save(out_file, "PNG", pnginfo=pnginfo)
    print(f"Generated Non-Payment Sample: {out_file}")
    return out_file


def generate_all_samples():
    """Generates all test samples in samples/ directory."""
    print("Generating CleanCheck test samples in:", SAMPLES_DIR)
    gen_file = generate_genuine_sample()
    generate_tampered_sample()
    generate_duplicate_sample(gen_file)
    generate_non_payment_sample()
    print("All samples created successfully.")


if __name__ == "__main__":
    generate_all_samples()
