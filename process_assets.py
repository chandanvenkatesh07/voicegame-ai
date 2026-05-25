"""Remove lime-green chroma-key backgrounds from generated PNG sprites.
Characters are generated on a flat #00FF00 background so white/cream fur
is never confused with the background — no interior holes possible.
"""
import colorsys
from pathlib import Path
from collections import deque
from PIL import Image

ASSETS_DIR = Path(__file__).parent / "assets"


def _is_green_bg(r, g, b):
    """True if pixel is the lime-green chroma-key background."""
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    # Lime green: hue 90-150°, high saturation, moderate-high brightness
    return 0.20 <= h <= 0.45 and s > 0.45 and v > 0.35


def remove_green_bg(path: Path):
    img  = Image.open(path).convert("RGBA")
    w, h = img.size
    data = list(img.getdata())

    # Flood-fill from all four edges — only through green pixels
    visited = bytearray(w * h)
    queue   = deque()

    def _is_bg_pixel(r, g, b, a):
        return _is_green_bg(r, g, b) or a < 10  # green OR already transparent from API

    def seed(x, y):
        idx = y * w + x
        r, g, b, a = data[idx]
        if not visited[idx] and _is_bg_pixel(r, g, b, a):
            visited[idx] = 1
            queue.append(idx)

    for x in range(w):
        seed(x, 0); seed(x, h - 1)
    for y in range(h):
        seed(0, y); seed(w - 1, y)

    while queue:
        idx = queue.popleft()
        cx, cy = idx % w, idx // w
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h:
                nidx = ny * w + nx
                if not visited[nidx]:
                    r, g, b, a = data[nidx]
                    if _is_bg_pixel(r, g, b, a):
                        visited[nidx] = 1
                        queue.append(nidx)

    # Make background transparent; soften the fringe edge
    new_data = []
    for idx, (r, g, b, a) in enumerate(data):
        if visited[idx]:
            new_data.append((r, g, b, 0))
        else:
            px, py = idx % w, idx // w
            near_bg = any(
                0 <= px + dx < w and 0 <= py + dy < h and visited[(py + dy) * w + (px + dx)]
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
            )
            if near_bg and _is_green_bg(r, g, b):
                # Fringe pixel that's still greenish — fade it out
                h_val, s_val, v_val = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                fade = s_val  # more saturated green = more transparent
                new_data.append((r, g, b, int(a * (1.0 - fade * 0.8))))
            else:
                new_data.append((r, g, b, a))

    img.putdata(new_data)
    img.save(path, "PNG")
    print(f"  ✅ Processed: {path.relative_to(ASSETS_DIR.parent)}")


if __name__ == "__main__":
    pngs = [p for p in ASSETS_DIR.rglob("*.png")
            if "backgrounds" not in str(p) and "generated" not in str(p)]
    print(f"\n🎨 Processing {len(pngs)} PNG assets (green chroma-key removal)...\n")
    for p in pngs:
        try:
            remove_green_bg(p)
        except Exception as e:
            print(f"  ❌ Failed {p.name}: {e}")
    print(f"\n✨ Done!")
