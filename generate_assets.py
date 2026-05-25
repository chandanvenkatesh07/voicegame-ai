"""
Generate pixel-art game assets using gpt-image-1.
Run once: python3 generate_assets.py
Delete existing PNGs first if you want to regenerate: rm assets/characters/*.png etc.
"""
import os
import asyncio
import base64
from pathlib import Path
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
BASE = Path(__file__).parent / "assets"

_PIXEL = (
    "pixel art sprite, 16-bit retro video game style, "
    "bold black outlines, crisp hard edges, limited color palette, "
    "no anti-aliasing, no gradients, no blurring, no shadows, "
    "full body visible, centered, transparent background"
)

ASSETS = {
    "characters/unicorn": (
        f"Adorable baby unicorn pixel art character, side-view facing right, "
        f"white body, rainbow mane and tail, gold horn, rosy cheeks, galloping pose. {_PIXEL}"
    ),
    "characters/bunny": (
        f"Adorable baby bunny pixel art character, side-view facing right, "
        f"white fluffy body, long pink-tipped ears, cotton tail, bounding leap pose. {_PIXEL}"
    ),
    "characters/dragon": (
        f"Cute baby dragon pixel art character, side-view facing right, "
        f"green scaly body, small wings spread, tiny flame from snout, playful pose. {_PIXEL}"
    ),
    "characters/cat": (
        f"Cute orange tabby kitten pixel art character, side-view facing right, "
        f"striped fur, perky ears, long curved tail, mid-run pose. {_PIXEL}"
    ),
    "characters/star_kid": (
        f"Cute living star pixel art character, five-pointed yellow star body, "
        f"tiny arms and legs, big dot eyes, cheerful waving pose. {_PIXEL}"
    ),
    "characters/fairy_sparkle": (
        f"Cute fairy pixel art character, floating pose, "
        f"golden hair, sparkling dress, butterfly wings, magic wand. {_PIXEL}"
    ),
    "collectibles/coin": (
        f"Gold coin collectible pixel art, round shiny coin, star emblem on face. "
        f"Pixel art, 16-bit retro style, bold outlines, transparent background, centered"
    ),
    "collectibles/gem": (
        f"Purple amethyst gem collectible pixel art, faceted diamond shape, glowing. "
        f"Pixel art, 16-bit retro style, bold outlines, transparent background, centered"
    ),
    "collectibles/star": (
        f"Glowing yellow five-pointed star collectible pixel art, sparkle effect. "
        f"Pixel art, 16-bit retro style, bold outlines, transparent background, centered"
    ),
    "collectibles/heart": (
        f"Red heart collectible pixel art, classic video game heart shape, glossy. "
        f"Pixel art, 16-bit retro style, bold outlines, transparent background, centered"
    ),
    "collectibles/cookie": (
        f"Round chocolate chip cookie collectible pixel art, smiley face icing. "
        f"Pixel art, 16-bit retro style, bold outlines, transparent background, centered"
    ),
    "obstacles/rock": (
        f"Grey boulder obstacle pixel art, grumpy face, mossy cracks. "
        f"Pixel art, 16-bit retro style, bold outlines, transparent background, centered"
    ),
    "obstacles/cloud": (
        f"Dark storm cloud obstacle pixel art, angry face, lightning bolt below. "
        f"Pixel art, 16-bit retro style, bold outlines, transparent background, centered"
    ),
    "obstacles/spike": (
        f"Purple metallic spike cluster obstacle pixel art, three sharp upward spikes. "
        f"Pixel art, 16-bit retro style, bold outlines, transparent background, centered"
    ),
    "obstacles/cactus": (
        f"Green cactus obstacle pixel art, grumpy face, two arms, red-tipped spines. "
        f"Pixel art, 16-bit retro style, bold outlines, transparent background, centered"
    ),
    # ── Fear-based obstacles ──────────────────────────────────────────────────
    "obstacles/wolf": (
        f"Menacing grey wolf obstacle pixel art, snarling teeth, hunched ready-to-pounce pose, "
        f"yellow glowing eyes, bushy tail raised. "
        f"Pixel art, 16-bit retro style, bold black outlines, transparent background, centered"
    ),
    "obstacles/fox": (
        f"Sneaky red fox obstacle pixel art, sly grin, tail curled up, orange-red fur, "
        f"white chest, pointy ears. "
        f"Pixel art, 16-bit retro style, bold black outlines, transparent background, centered"
    ),
    "obstacles/hawk": (
        f"Fierce hawk obstacle pixel art, wings spread wide diving pose, sharp talons, "
        f"fierce eyes, brown feathers with white chest. "
        f"Pixel art, 16-bit retro style, bold black outlines, transparent background, centered"
    ),
    "obstacles/knight": (
        f"Armored knight obstacle pixel art, full plate armor, sword raised, visor down, "
        f"red cape, shield with cross emblem. "
        f"Pixel art, 16-bit retro style, bold black outlines, transparent background, centered"
    ),
    "obstacles/dog": (
        f"Aggressive bulldog obstacle pixel art, barking wide mouth, stocky body, "
        f"spiked collar, brown and white fur, stubby legs. "
        f"Pixel art, 16-bit retro style, bold black outlines, transparent background, centered"
    ),
    "obstacles/dark_wizard": (
        f"Dark wizard obstacle pixel art, black hooded robe, glowing purple staff, "
        f"casting spell effect, evil red eyes under hood. "
        f"Pixel art, 16-bit retro style, bold black outlines, transparent background, centered"
    ),
    "obstacles/ice_crystal": (
        f"Jagged ice crystal cluster obstacle pixel art, sharp frozen spikes pointing up, "
        f"icy blue-white color, glowing cold light effect. "
        f"Pixel art, 16-bit retro style, bold black outlines, transparent background, centered"
    ),
    "obstacles/spider": (
        f"Giant scary spider obstacle pixel art, eight hairy legs spread out, "
        f"red hourglass marking, multiple evil eyes, fangs dripping. "
        f"Pixel art, 16-bit retro style, bold black outlines, transparent background, centered"
    ),
    "obstacles/black_hole": (
        f"Black hole obstacle pixel art, swirling dark vortex, purple and dark blue spiral, "
        f"glowing event horizon ring, stars being sucked in. "
        f"Pixel art, 16-bit retro style, bold black outlines, transparent background, centered"
    ),
    "obstacles/barrel": (
        f"Wooden barrel obstacle pixel art, rolling forward, iron bands, cracked wood, "
        f"small angry face on front. "
        f"Pixel art, 16-bit retro style, bold black outlines, transparent background, centered"
    ),
    "obstacles/bomb": (
        f"Round bomb obstacle pixel art, classic black cannonball with lit fuse sparking, "
        f"angry face, round shiny surface. "
        f"Pixel art, 16-bit retro style, bold black outlines, transparent background, centered"
    ),
}


async def generate_one(key: str, prompt: str, semaphore: asyncio.Semaphore):
    out_path = BASE / (key + ".png")
    if out_path.exists():
        print(f"  ✓ Already exists: {key}.png")
        return

    async with semaphore:
        print(f"  🎨 Generating: {key}...")
        for attempt in range(5):
            try:
                response = await client.images.generate(
                    model="gpt-image-1",
                    prompt=prompt,
                    size="1024x1024",
                    quality="medium",
                    background="transparent",
                    n=1,
                )
                img_bytes = base64.b64decode(response.data[0].b64_json)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(img_bytes)
                print(f"  ✅ Saved: {key}.png")
                await asyncio.sleep(13)
                return
            except Exception as e:
                if "429" in str(e):
                    wait = 15 * (attempt + 1)
                    print(f"  ⏳ Rate limited, waiting {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    print(f"  ❌ Failed {key}: {e}")
                    return


async def main():
    print(f"\n🎮 Pixel Art Asset Generator")
    print(f"   Generating {len(ASSETS)} assets...\n")
    semaphore = asyncio.Semaphore(1)
    tasks = [generate_one(key, prompt, semaphore) for key, prompt in ASSETS.items()]
    await asyncio.gather(*tasks)
    print("\n✨ All done! Assets saved to assets/")


if __name__ == "__main__":
    asyncio.run(main())
