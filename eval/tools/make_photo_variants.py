"""Make phone-photo-like copies of some clean mock bills.

Each variant goes to eval/bills/<id>-photo/bill.jpg with the same fields as the source label and
difficulty "phone_photo". Effects: paper placed on a table-like background, perspective warp, 3-8 degree
rotation, uneven light with a soft shadow, mild blur, sensor noise, JPEG quality ~60. Seeds are fixed so
the output is the same each run.

Usage:
    uv run --with opencv-python-headless --with numpy --with pillow python eval/tools/make_photo_variants.py [ids...]
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from billkit import BILLS_DIR, MAX_BYTES, MAX_SIDE  # noqa: E402

# id -> (seed, rotation degrees, warp strength, blur sigma, light direction)
VARIANTS = {
    "delhi-brpl-hindi-clean-01": (11, 4.0, 0.05, 1.0, "left"),
    "msedcl-marathi-devanagari-01": (12, -5.5, 0.07, 1.2, "top"),
    "tnpdcl-tamil-bimonthly-01": (13, 7.0, 0.04, 0.9, "right"),
    "bescom-kannada-01": (14, -3.5, 0.06, 1.1, "bottom"),
    "adani-mumbai-solar-english-01": (15, 6.0, 0.05, 1.3, "left"),
    "uppcl-hindi-arrears-01": (16, -8.0, 0.08, 1.0, "top"),
}


def table_background(h, w, rng):
    """Wood-ish or fabric-ish table surface."""
    base = np.array(rng.choice([[120, 92, 64], [150, 135, 115], [70, 70, 75], [180, 170, 150]]), np.float32)
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    grain = 12 * np.sin(2 * np.pi * (y * rng.uniform(15, 40) + 0.3 * np.sin(2 * np.pi * x * 2)))
    noise = cv2.GaussianBlur(rng.normal(0, 18, (h, w)).astype(np.float32), (0, 0), 3)
    bg = base[None, None, :] + (grain + noise)[..., None]
    return np.clip(bg, 0, 255).astype(np.float32)


def light_mask(h, w, direction, rng):
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    g = {"left": 1 - x, "right": x, "top": 1 - y, "bottom": y}[direction] * np.ones((h, w), np.float32)
    mask = 0.72 + 0.38 * g  # brighter on one side
    # a soft shadow blob (hand or phone) on the darker side
    cy, cx = rng.uniform(0.2, 0.8) * h, rng.uniform(0.2, 0.8) * w
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    blob = np.exp(-(((yy - cy) / (0.35 * h)) ** 2 + ((xx - cx) / (0.25 * w)) ** 2))
    mask *= 1 - 0.22 * blob
    return mask


def make_variant(src_id: str, seed: int, rot: float, warp: float, blur: float, light: str) -> Path:
    rng = np.random.default_rng(seed)
    src_dir = BILLS_DIR / src_id
    src = next(src_dir.glob("bill.*"))
    paper = cv2.cvtColor(np.array(Image.open(src).convert("RGB")), cv2.COLOR_RGB2BGR).astype(np.float32)
    # slightly warm, off-white paper
    paper = paper * np.array([0.93, 0.96, 0.98], np.float32) + 4
    ph, pw = paper.shape[:2]

    pad = int(0.16 * max(ph, pw))
    H, W = ph + 2 * pad, pw + 2 * pad
    canvas = table_background(H, W, rng)

    # destination corners: paper corners, jittered for a perspective look, then rotated about the centre
    src_pts = np.float32([[0, 0], [pw, 0], [pw, ph], [0, ph]])
    j = warp * min(pw, ph)
    dst = np.float32([[pad, pad], [pad + pw, pad], [pad + pw, pad + ph], [pad, pad + ph]])
    dst += rng.uniform(-j, j, dst.shape).astype(np.float32)
    # keep the top edge a bit narrower than the bottom (camera tilted toward the top)
    dst[0, 0] += j * 0.6
    dst[1, 0] -= j * 0.6
    c = np.float32([W / 2, H / 2])
    t = np.deg2rad(rot)
    R = np.float32([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
    dst = (dst - c) @ R.T + c
    M = cv2.getPerspectiveTransform(src_pts, dst)

    warped = cv2.warpPerspective(paper, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
    m = cv2.warpPerspective(np.ones((ph, pw), np.float32), M, (W, H), flags=cv2.INTER_LINEAR)
    # drop shadow under the paper
    shadow = cv2.GaussianBlur(cv2.warpPerspective(np.ones((ph, pw), np.float32), M, (W, H)), (0, 0), pad / 8)
    shadow = np.roll(shadow, (int(pad * 0.06), int(pad * 0.06)), (0, 1))
    canvas *= (1 - 0.45 * shadow)[..., None]
    out = warped * m[..., None] + canvas * (1 - m[..., None])

    out *= light_mask(H, W, light, rng)[..., None]
    out = cv2.GaussianBlur(out, (0, 0), blur)
    out += rng.normal(0, 4.5, out.shape).astype(np.float32)
    out = np.clip(out, 0, 255).astype(np.uint8)

    # crop to the paper area with a little margin, like a framed phone photo
    ys, xs = np.where(m > 0.5)
    mg = int(0.05 * max(ph, pw))
    y0, y1 = max(0, ys.min() - mg), min(H, ys.max() + mg)
    x0, x1 = max(0, xs.min() - mg), min(W, xs.max() + mg)
    out = out[y0:y1, x0:x1]

    img = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
    s = min(1.0, MAX_SIDE / max(img.size))
    if s < 1:
        img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)

    dst_id = f"{src_id}-photo"
    dst_dir = BILLS_DIR / dst_id
    dst_dir.mkdir(parents=True, exist_ok=True)
    for old in dst_dir.glob("bill.*"):
        old.unlink()
    q = 60
    while True:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=q)
        if buf.tell() < MAX_BYTES or q <= 40:
            break
        q -= 5
    p = dst_dir / "bill.jpg"
    p.write_bytes(buf.getvalue())

    label = json.loads((src_dir / "label.json").read_text(encoding="utf-8"))
    label["id"] = dst_id
    label["difficulty"] = "phone_photo"
    label["notes"] = (f"Photo-like copy of {src_id} (perspective warp, {abs(rot):g} degree rotation, uneven "
                      f"light from the {light}, blur, noise, JPEG q{q}). Same fields. Original notes: "
                      + label["notes"])
    (dst_dir / "label.json").write_text(json.dumps(label, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


if __name__ == "__main__":
    only = set(sys.argv[1:])
    for sid, args in VARIANTS.items():
        if only and sid not in only:
            continue
        p = make_variant(sid, *args)
        print(f"{p.parent.name:<40} {Image.open(p).size} {p.stat().st_size // 1024} KB")
