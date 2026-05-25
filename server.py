import os
import json
import uuid
import re
import io
import base64
import hashlib
from pathlib import Path
from PIL import Image
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", "8001"))
BASE_URL = f"http://localhost:{PORT}"

app = FastAPI()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL      = os.getenv("OPENAI_MODEL",      "gpt-4.1")
MODEL_CODE = os.getenv("OPENAI_MODEL_CODE", "o3")       # used for Three.js game generation

BASE_DIR = Path(__file__).parent
GAMES_DIR = BASE_DIR / "games"
GAMES_DIR.mkdir(exist_ok=True)

app.mount("/assets", StaticFiles(directory=BASE_DIR / "assets"), name="assets")
app.mount("/games", StaticFiles(directory=GAMES_DIR), name="games")

# Serve frontend files with no-cache so changes are always picked up
@app.get("/frontend/{filename:path}")
async def frontend_file(filename: str):
    path = BASE_DIR / "frontend" / filename
    if not path.exists():
        return Response(status_code=404)
    resp = FileResponse(path)
    resp.headers["Cache-Control"] = "no-store"
    return resp


# Serve any asset with white background removed (for Three.js PNG sprite billboards)
_transparent_cache: dict = {}

def _make_placeholder_png(path: str) -> bytes:
    """Return a colored shape PNG so Phaser never gets a 404 for a missing sprite."""
    from PIL import ImageDraw
    size = 128
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if "collectible" in path or "coin" in path or "star" in path or "gem" in path or "heart" in path:
        color = (251, 191, 36, 255)   # gold
    elif "obstacle" in path or "rock" in path or "cloud" in path or "spike" in path or "cactus" in path:
        color = (239, 68, 68, 255)    # red
    else:
        color = (99, 102, 241, 255)   # indigo (character placeholder)
    draw.ellipse([8, 8, size - 8, size - 8], fill=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

@app.get("/transparent-asset/{path:path}")
async def transparent_asset(path: str):
    if path in _transparent_cache:
        return Response(content=_transparent_cache[path], media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})
    asset_path = BASE_DIR / "assets" / path
    if not asset_path.exists():
        return Response(content=_make_placeholder_png(path), media_type="image/png",
                        headers={"Cache-Control": "no-store"})
    png_bytes = asset_path.read_bytes()
    _transparent_cache[path] = png_bytes
    return Response(content=png_bytes, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


FAIRY_SYSTEM_PROMPT = """You are Sparkle, a magical fairy who helps kids aged 4-8 create their very own video games!
You speak in a warm, encouraging, playful way. Use simple words a young child understands.
Keep your responses SHORT — 2-3 sentences maximum. Kids have short attention spans!

Your job is to ask questions one at a time to design a game. Be patient — kids may give silly or unclear answers, and that's totally fine!
If a child's answer is unclear, guess a fun option and ask if they like it, or give them 2 simple choices.
If they say something unexpected, go with it enthusiastically!

You need to collect this information (one question at a time, in order):
1. game_type: What kind of game? (jumping/running/flying/catching/avoiding things) — give fun examples
2. character: Who does the player play as? (unicorn/bunny/dragon/cat/star — or their own idea)
3. world: Where does the game happen? (rainbow land/forest/space/ocean/candy world)
4. collectible: What do they collect? (stars/coins/gems/hearts/cookies/rainbows)
5. obstacle: What do they avoid? (rocks/clouds/spikes/monsters/grumpy cactus)
6. game_name: What's the game called?

Track what you've collected in your reasoning. Once you have ALL 6 pieces of info, respond with EXACTLY this JSON at the end of your message (keep your friendly message before it):
<GAME_READY>{"game_type":"...","character":"...","world":"...","collectible":"...","obstacle":"...","game_name":"..."}</GAME_READY>

Always start with: "Hello! I'm Sparkle the magic fairy! ✨ I'm going to help you make your very own video game! Are you ready? First question..."
Be enthusiastic with stars ✨ and magic words! Never use scary or sad themes."""

GAME_GENERATOR_PROMPT = """You are an expert Phaser 3 game developer making fun games for children aged 4-8.

Generate ONLY JavaScript that creates a complete Phaser 3 game using the globally available:
- CHAR_URL, COLL_URL, OBS_URL  — URLs of pre-generated 3D PNG sprite images (white backgrounds)
- GAME_NAME                     — string title of the game
- PHASER_GRAVITY = 500          — use this for arcade gravity y
- JUMP_VELOCITY = -420          — use this for player jump (setVelocityY)
- PLAYER_SPEED = 180            — use this for left/right movement
- OBS_SPEED_START = 130         — starting obstacle speed (px/s)
- OBS_SPEED_MAX = 220           — max obstacle speed
- OBS_SPEED_STEP = 15           — speed increase per collect

STRUCTURE — create exactly these three Phaser Scene classes then call new Phaser.Game():

class BootScene extends Phaser.Scene — shows the game title and a big PLAY button/text.
  - constructor: super({key:'Boot'})
  - preload: load all 3 images using CHAR_URL, COLL_URL, OBS_URL with keys 'character','collectible','obstacle'
  - create: draw colorful background, large title text, "Press SPACE or click to play!" text
  - update: if spacebar pressed or pointer clicked → this.scene.start('Game')

class GameScene extends Phaser.Scene — the main gameplay.
  - constructor: super({key:'Game'})
  - create():
    • Draw a beautiful colorful sky/world background using graphics (gradient sky, bright ground strip, decorations)
    • Add ground platform: this.physics.add.staticGroup() — a wide invisible ground at y=500
    • Player: this.physics.add.image(120, 400, 'character').setScale(0.1)
      → setCollideWorldBounds(true), setBlendMode(1)  (removes white bg via multiply)
    • this.physics.add.collider(player, ground)
    • cursors = this.input.keyboard.createCursorKeys()
    • spaceKey = this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE)
    • Collectibles group: this.physics.add.staticGroup() — spawn 5 at random x/y above ground
      → each setScale(0.06), setBlendMode(1)
    • this.physics.add.overlap(player, collectibles, collectItem, null, this)
    • Obstacle timer: this.time.addEvent({delay:2200, callback:spawnObstacle, loop:true})
    • obstacles = this.physics.add.group()
    • this.physics.add.overlap(player, obstacles, hitObstacle, null, this)
    • score=0, lives=3, obstacleSpeed=OBS_SPEED_START
    • Score text: this.add.text(20,16,'⭐ 0 / 10',{fontSize:'26px',fill:'#fff',fontFamily:'Comic Sans MS'})
    • Lives text: this.add.text(760,16,'❤️❤️❤️',{fontSize:'26px'})
    • invincible=false
  - update():
    • Left/right movement: use cursors.left/right and PLAYER_SPEED. Set velocityX=0 when no key.
    • Jump: if (cursors.up.isDown || spaceKey.isDown) AND player.body.blocked.down → setVelocityY(JUMP_VELOCITY)
    • Move obstacles left each frame: obstacles.children.iterate(o => { o.x -= obstacleSpeed * (1/60); if(o.x < -100) o.destroy(); })
  - collectItem(player, item):
    • item.destroy(), score++, update score text
    • Play collect sound (WebAudio beep: freq 880 dur 0.15)
    • Increase speed every 3 collects: obstacleSpeed = Math.min(obstacleSpeed+OBS_SPEED_STEP, OBS_SPEED_MAX)
    • Spawn replacement collectible
    • If score >= 10 → this.scene.start('End', {won:true, score})
  - hitObstacle(player, obstacle):
    • if invincible return
    • obstacle.destroy(), lives--, update lives text
    • Play hit sound. Set invincible=true, flash player with tween
    • this.time.delayedCall(2000, ()=>invincible=false)
    • If lives <= 0 → this.scene.start('End', {won:false, score})
  - spawnObstacle():
    • let o = obstacles.create(920, 420, 'obstacle').setScale(0.08).setBlendMode(1)
    • o.body.allowGravity = false
    • IMPORTANT: randomize Y between 380–450 so some are jumpable
    • Vary spawn delay slightly for fairness

class EndScene extends Phaser.Scene — win or lose screen.
  - constructor: super({key:'End'})
  - init(data): store data.won and data.score
  - create():
    • Colorful background
    • Big text: won ? '🎉 YOU WIN! 🎉' : '💪 Try Again!'
    • Score display if won
    • "Press SPACE or click to play again" — restart back to 'Boot'
  - update(): space or click → this.scene.start('Boot')

Phaser.Game config:
  type: Phaser.AUTO
  width: 900, height: 560
  backgroundColor: '#87CEEB'
  physics: { default:'arcade', arcade:{ gravity:{y: PHASER_GRAVITY}, debug:false } }
  scene: [BootScene, GameScene, EndScene]
  parent: document.body
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH }

Output ONLY raw JavaScript — no HTML tags, no markdown fences, no explanation."""


DIFFICULTY_CONFIGS = {
    "none":   {"speed_0":90,  "speed_max":130, "win":8,  "lives":5, "obs_interval":3800, "speed_inc":5},
    "low":    {"speed_0":140, "speed_max":220, "win":10, "lives":3, "obs_interval":2200, "speed_inc":15},
    "medium": {"speed_0":200, "speed_max":340, "win":12, "lives":3, "obs_interval":1700, "speed_inc":20},
    "high":   {"speed_0":260, "speed_max":440, "win":15, "lives":2, "obs_interval":1300, "speed_inc":25},
}


class ChatMessage(BaseModel):
    message: str
    history: list[dict]
    session_id: str = ""


class GenerateGameRequest(BaseModel):
    requirements: dict
    session_id: str = ""


class SpeakRequest(BaseModel):
    text: str
    voice: str = "shimmer"


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(BASE_DIR / "frontend" / "index.html")


@app.post("/speak")
async def speak_tts(req: SpeakRequest):
    clean = req.text.replace("✨","").replace("⭐","").replace("💫","").replace("🌟","")[:500]
    response = await client.audio.speech.create(
        model="tts-1",
        voice=req.voice,
        input=clean,
        speed=0.9,
    )
    return Response(content=response.content, media_type="audio/mpeg",
                    headers={"Cache-Control": "no-store"})


@app.post("/chat")
async def chat(req: ChatMessage):
    messages = [{"role": "system", "content": FAIRY_SYSTEM_PROMPT}]
    for h in req.history:
        messages.append(h)
    messages.append({"role": "user", "content": req.message})

    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=300,
        temperature=0.85,
    )

    reply = response.choices[0].message.content
    game_ready = None

    match = re.search(r"<GAME_READY>(.*?)</GAME_READY>", reply, re.DOTALL)
    if match:
        try:
            game_ready = json.loads(match.group(1))
            reply = reply[: match.start()].strip()
        except json.JSONDecodeError:
            pass

    return {"reply": reply, "game_ready": game_ready}


ASSET_BASE = f"{BASE_URL}/assets"

# Map kid's answer keywords → asset filenames
CHARACTER_MAP = {
    "unicorn": "characters/unicorn",
    "bunny": "characters/bunny", "rabbit": "characters/bunny",
    "dragon": "characters/dragon",
    "cat": "characters/cat", "kitten": "characters/cat",
    "star": "characters/star_kid", "star_kid": "characters/star_kid",
}
COLLECTIBLE_MAP = {
    "coin": "collectibles/coin", "coins": "collectibles/coin", "gold": "collectibles/coin",
    "gem": "collectibles/gem", "gems": "collectibles/gem", "crystal": "collectibles/gem",
    "star": "collectibles/star", "stars": "collectibles/star",
    "heart": "collectibles/heart", "hearts": "collectibles/heart",
    "cookie": "collectibles/cookie", "cookies": "collectibles/cookie",
}
OBSTACLE_MAP = {
    "rock": "obstacles/rock", "rocks": "obstacles/rock", "boulder": "obstacles/rock",
    "cloud": "obstacles/cloud", "clouds": "obstacles/cloud", "storm": "obstacles/cloud",
    "spike": "obstacles/spike", "spikes": "obstacles/spike",
    "cactus": "obstacles/cactus",
}


def resolve_asset(answer: str, mapping: dict, fallback: str) -> str:
    answer_lower = answer.lower()
    for key, path in mapping.items():
        if key in answer_lower:
            asset_file = BASE_DIR / "assets" / (path + ".png")
            if asset_file.exists():
                return f"{ASSET_BASE}/{path}.png"
    fallback_file = BASE_DIR / "assets" / (fallback + ".png")
    if fallback_file.exists():
        return f"{ASSET_BASE}/{fallback}.png"
    return ""


# World → (sky_top, sky_bottom, ground_hex) color themes
WORLD_THEMES = {
    "rainbow":    ("#c084fc", "#fb923c", "4ade80"),
    "forest":     ("#86efac", "#4ade80", "16a34a"),
    "space":      ("#0f0728", "#1e1b4b", "312e81"),
    "ocean":      ("#0ea5e9", "#38bdf8", "d97706"),
    "candy":      ("#f472b6", "#fb923c", "f43f5e"),
    "underwater": ("#06b6d4", "#0284c7", "ca8a04"),
    "desert":     ("#fb923c", "#fbbf24", "d97706"),
    "sky":        ("#7dd3fc", "#bfdbfe", "86efac"),
    "default":    ("#60a5fa", "#bfdbfe", "4ade80"),
}

# Keywords that map to each theme — checked in order (space before desert so "space cowboy" → space)
WORLD_KEYWORDS = {
    "space":      ["space","galaxy","planet","cosmos","cosmic","stellar","lunar","nebula",
                   "meteor","asteroid","orbit","alien","rocket","astronaut","interstellar","galactic","star wars"],
    "underwater": ["underwater","submarine","deep sea","abyss","reef","kelp","seaweed","coral reef"],
    "ocean":      ["ocean","sea","marine","aquatic","fish","beach","wave","nautical","island","lagoon"],
    "forest":     ["forest","jungle","tree","wood","woods","nature","grove","woodland","enchanted"],
    "candy":      ["candy","sweet","sugar","chocolate","dessert","cookie","cake","lollipop","gumdrop","gummy"],
    "desert":     ["desert","sand","sahara","dune","arid","western","wild west","cowboy"],
    "sky":        ["sky","cloud","heaven","floating island","air","wind","high altitude"],
    "rainbow":    ["rainbow","colorful","multicolor","prism","spectrum","magical color"],
}

def world_theme(world: str):
    w = world.lower()
    for key, keywords in WORLD_KEYWORDS.items():
        if any(kw in w for kw in keywords):
            return (*WORLD_THEMES[key], key)
    return (*WORLD_THEMES["default"], "default")


GAME_TEMPLATES = {
    "runner":  "game_shell_runner.html",
    "flyer":   "game_shell_flyer.html",
    "shooter": "game_shell_shooter.html",
}

@app.post("/generate-game")
async def generate_game(req: GenerateGameRequest):
    r = req.requirements

    # Custom URLs from on-demand image generation take priority
    char_url = (r.get("char_url_override") or
                resolve_asset(r.get("character",""), CHARACTER_MAP, "characters/bunny"))
    coll_url = (r.get("coll_url_override") or
                resolve_asset(r.get("collectible",""), COLLECTIBLE_MAP, "collectibles/star"))
    obs_url  = (r.get("obs_url_override") or
                resolve_asset(r.get("obstacle",""), OBSTACLE_MAP, "obstacles/rock"))

    game_name          = r.get("game_name", "My Amazing Game")
    sky_top, sky_bot, ground_hex, world_key = world_theme(r.get("world", ""))

    game_type     = r.get("game_type", "runner").lower()
    template_name = GAME_TEMPLATES.get(game_type, "game_shell_runner.html")

    difficulty = r.get("difficulty", "low")
    if isinstance(difficulty, dict):
        diff_config = difficulty  # frontend sent the full config object directly
    else:
        diff_config = DIFFICULTY_CONFIGS.get(str(difficulty).lower(), DIFFICULTY_CONFIGS["low"])
    diff_json     = json.dumps(diff_config)

    # Generate background image — driven by the full game concept description from LLM
    try:
        bg_url = await generate_background_image(r.get("bg_description", ""))
    except Exception:
        bg_url = ""

    shell = (BASE_DIR / "templates" / template_name).read_text(encoding="utf-8")
    voice_on  = "true" if r.get("voice_on", True) else "false"

    game_html = (shell
        .replace("{{GAME_NAME}}",    game_name)
        .replace("{{GAME_NAME_JS}}", json.dumps(game_name))
        .replace("{{VOICE_ON}}",     voice_on)
        .replace("{{CHAR_URL}}",     char_url)
        .replace("{{COLL_URL}}",    coll_url)
        .replace("{{OBS_URL}}",     obs_url)
        .replace("{{BG_URL}}",      bg_url)
        .replace("{{SKY_TOP}}",     sky_top)
        .replace("{{SKY_BOT}}",     sky_bot)
        .replace("{{GROUND_HEX}}",  ground_hex)
        .replace("{{WORLD_KEY}}",   world_key)
        .replace("{{DIFF_JSON}}",   diff_json)
    )

    session_id = req.session_id or str(uuid.uuid4())[:8]
    safe_name  = re.sub(r"[^a-z0-9_]", "_", game_name.lower())[:30]
    filename   = f"{safe_name}_{session_id}.html"
    (GAMES_DIR / filename).write_text(game_html, encoding="utf-8")

    return {"game_url": f"{BASE_URL}/games/{filename}", "filename": filename}


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL}


# ── LLM prompts ───────────────────────────────────────────────────────────────

EXTRACT_PARAMS_PROMPT = """You are a game parameter extractor for a children's voice-first game maker.
A child (aged 4-8) has described their dream game out loud. Extract structured parameters.

Preset assets available:
  characters  : unicorn, bunny, dragon, cat   ← ONLY these four need no custom image
  collectibles: stars, coins, gems, hearts    ← ONLY these four need no custom image
  obstacles   : rocks, clouds, spikes, cactus ← ONLY these four need no custom image
  game_types  : runner (run and jump), flyer (fly up/down), shooter (shoot enemies)

Game type mapping:
  - flying/soaring/flapping/wings → flyer
  - shooting/blasting/zapping/laser → shooter
  - running/jumping/hopping/racing/bouncing/skipping → runner
  - space, planets, cowboys, animals → default to runner unless flying is explicit
  - if ambiguous → runner

Custom asset rules (IMPORTANT — apply strictly):
  All custom prompts MUST be pixel art style: "pixel art sprite, 16-bit retro game style, bold black outlines, crisp hard edges, limited color palette, transparent background, centered"
  - characters: ONLY unicorn/bunny/dragon/cat need no custom image. Everything else
    (cowboy, robot, knight, dinosaur, wizard, princess, alien, astronaut, etc.)
    → set needs_custom_char=true and write a vivid pixel art custom_char_prompt
  - obstacles: ONLY rocks/clouds/spikes/cactus need no custom image. Everything else
    (planets, boulders, volcanoes, icebergs, cookies, cars, trees, etc.)
    → set needs_custom_obs=true and write a vivid pixel art custom_obs_prompt
  - collectibles: ONLY stars/coins/gems/hearts need no custom image. Everything else
    → set needs_custom_coll=true and write a vivid pixel art custom_coll_prompt

World naming (CRITICAL — use keywords so the game engine picks the right theme):
  - Space/galaxy/planets/astronauts → include "space" or "galaxy" in the world name
    e.g. "outer space", "space cowboy galaxy", "alien planet"
  - Forest/trees/jungle → include "forest" or "jungle"
  - Ocean/sea/fish/beach → include "ocean" or "sea"
  - Candy/sweets/sugar → include "candy" or "sweet"
  - Underwater/coral → include "underwater"
  - Desert/sand/cowboy → include "desert" or "wild west"
  - Sky/clouds/islands → include "sky" or "cloud"
  - Rainbow/colorful → include "rainbow" or "colorful"

GameSpec v2 — archetype mapping (pick the ONE best fit):
  free-flight-rescue  : hero flies freely in 8 directions and rescues/collects trapped things
                        → triggers: rescue, save, free, help, protect + flying OR dragon + save/rescue
  magic-cleanse       : hero zaps/transforms enemies/clouds/monsters with magic projectiles
                        → triggers: zap, shoot, blast, cleanse, transform, magic attack, wizard/witch shooting
  collector-adventure : auto-running hero collects specific named items, dodges obstacles
                        → triggers: collect, grab, gather, adventure, find, most default running games
  lane-dodge          : hero in fixed lanes dodges or catches falling/incoming objects
                        → triggers: dodge, catch, race, lane, swerve, avoid
  platform-jumper     : hero jumps between platforms to reach the top/goal
                        → triggers: hop, bounce, jump between things, climb, reach the top, platform

  Default: collector-adventure (if none of the above clearly apply)

Main verb — the single core action word the player performs:
  rescue | collect | zap | dodge | jump | fly | catch | climb | save | explore

Win story — personalized one-sentence celebration, 8–12 words, child's name placeholder = "You":
  free-flight-rescue  → "You rescued all the [collectibles]! Every one is safe!"
  magic-cleanse       → "You cleansed the whole [world]! The magic is restored!"
  collector-adventure → "You collected all the [collectibles]! Amazing adventure!"
  lane-dodge          → "You dodged everything and made it to the finish!"
  platform-jumper     → "You reached the top of [world]! You're a champion!"

Return ONLY valid JSON with exactly these fields:
{
  "game_type": "runner|flyer|shooter",
  "character": "preset name or brief description",
  "collectible": "preset name or brief description",
  "obstacle": "preset name or brief description",
  "world": "descriptive world name including a theme keyword from the list above",
  "game_name": "Fun title with exclamation!",
  "needs_custom_char": false,
  "needs_custom_coll": false,
  "needs_custom_obs": false,
  "custom_char_prompt": "Adorable [desc] pixel art character sprite, full body side-view facing right, 16-bit retro game style, bold black outlines, crisp hard edges, limited color palette, transparent background, no anti-aliasing, no gradients, centered",
  "custom_coll_prompt": "",
  "custom_obs_prompt": "",
  "understood": "Enthusiastic one-sentence summary of what the child described",
  "player_fantasy": "I am a [character] who [main_verb]s in [world]",
  "main_verb": "rescue|collect|zap|dodge|jump|fly|catch|climb|save|explore",
  "archetype": "free-flight-rescue|magic-cleanse|collector-adventure|lane-dodge|platform-jumper",
  "win_story": "Short personalized win celebration sentence",
  "bg_description": "Vivid 1-sentence pixel art environment description for a 16-bit SNES-style side-scrolling game background — describe ONLY the world/setting (no characters), highly specific to THIS exact game concept. Use concrete pixel-art-renderable nouns. Examples: 'Outer space pixel art with twinkling stars, colorful nebulae, ringed planets, and asteroid clusters in deep blues and purples'; 'Lush pixel art forest with layered trees, glowing mushrooms, mossy rocks, and shafts of golden light'; 'Candy land pixel art with giant lollipops, chocolate rivers, gumdrop hills, and cotton candy clouds'. Make it unique to the character+world+collectible+obstacle combo."
}"""

STORY_PROMPT = """You are Sparkle, a magical fairy storyteller for children aged 4-8.
Write a 2-sentence adventure story about the child's game hero.
Use simple, exciting words. First sentence: introduce the hero and their magical world.
Second sentence: their quest and challenge. End with 'Let\'s go!' or 'Adventure awaits!'.
Maximum 35 words. No emojis. No special characters."""

IMAGE_STYLE_SUFFIX = (
    ", pixel art sprite, 16-bit retro video game style, "
    "bold black outlines, crisp hard edges, limited color palette, "
    "no anti-aliasing, no gradients, full body visible, centered, transparent background"
)

_BG_STYLE = (
    "pixel art game background, 16-bit SNES retro style, "
    "wide side-scrolling platformer level background, "
    "crisp pixel art with bold colors, multiple parallax depth layers, "
    "detailed pixel art environment, vibrant saturated palette, "
    "no characters, no text, no UI elements, no anti-aliasing"
)


async def generate_background_image(bg_description: str) -> str:
    """Generate (and cache) a landscape background from a full scene description."""
    bg_dir = BASE_DIR / "assets" / "backgrounds"
    bg_dir.mkdir(exist_ok=True)

    if not bg_description:
        bg_description = "magical colorful fantasy land, rolling hills, bright sky"

    prompt = f"Game level background: {bg_description}. {_BG_STYLE}"
    phash  = hashlib.md5(prompt.encode()).hexdigest()[:10]
    cached = bg_dir / f"{phash}.png"
    if cached.exists():
        return f"{ASSET_BASE}/backgrounds/{phash}.png"

    response = await client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        n=1,
        size="1536x1024",
        quality="high",
    )
    img_bytes = base64.b64decode(response.data[0].b64_json)
    cached.write_bytes(img_bytes)
    return f"{ASSET_BASE}/backgrounds/{phash}.png"


# ── Image generation helper ───────────────────────────────────────────────────

async def generate_and_save_image(prompt: str, filename: str) -> str:
    gen_dir = BASE_DIR / "assets" / "generated"
    gen_dir.mkdir(exist_ok=True)

    # Cache by prompt hash
    phash    = hashlib.md5(prompt.encode()).hexdigest()[:10]
    cached   = gen_dir / f"{phash}.png"
    if cached.exists():
        return f"{ASSET_BASE}/generated/{phash}.png"

    response = await client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        n=1,
        size="1024x1024",
        background="transparent",
    )
    img_bytes = base64.b64decode(response.data[0].b64_json)
    cached.write_bytes(img_bytes)
    return f"{ASSET_BASE}/generated/{phash}.png"


# ── New models ────────────────────────────────────────────────────────────────

class ExtractParamsRequest(BaseModel):
    transcript: str
    session_id: str = ""

class GenerateStoryRequest(BaseModel):
    params: dict

class GenerateCustomImageRequest(BaseModel):
    prompt: str
    filename: str = ""


# ── New endpoints ─────────────────────────────────────────────────────────────

@app.post("/extract-params")
async def extract_params(req: ExtractParamsRequest):
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": EXTRACT_PARAMS_PROMPT},
            {"role": "user",   "content": req.transcript},
        ],
        response_format={"type": "json_object"},
        max_tokens=500,
        temperature=0.7,
    )
    return json.loads(response.choices[0].message.content)


@app.post("/generate-story")
async def generate_story(req: GenerateStoryRequest):
    p = req.params
    user_msg = (
        f"Hero: {p.get('character','a brave hero')}. "
        f"World: {p.get('world','a magical land')}. "
        f"Collecting: {p.get('collectible','treasures')}. "
        f"Avoiding: {p.get('obstacle','dangers')}. "
        f"Game: {p.get('game_name','My Adventure')}."
    )
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": STORY_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        max_tokens=100,
        temperature=0.95,
    )
    return {"story": response.choices[0].message.content.strip()}


@app.post("/generate-custom-image")
async def generate_custom_image(req: GenerateCustomImageRequest):
    try:
        full_prompt = req.prompt + IMAGE_STYLE_SUFFIX
        url = await generate_and_save_image(full_prompt, req.filename)
        return {"url": url, "ok": True}
    except Exception as e:
        return {"url": "", "ok": False, "error": str(e)}


class GenerateThreeJSRequest(BaseModel):
    description: str
    session_id:  str = ""
    gamespec:    dict = {}
    char_url:    str  = ""   # PNG sprite URL for the hero character
    coll_url:    str  = ""   # PNG sprite URL for collectibles
    obs_url:     str  = ""   # PNG sprite URL for obstacles

def _load_system_prompt() -> str:
    return (BASE_DIR / "GAME_GENERATION_PROMPT.md").read_text(encoding="utf-8")

def _strip_fences(text: str) -> str:
    """Extract raw HTML from model output — handles fences, preamble, and trailing prose."""
    text = text.strip()
    # If there's a ```html or ``` fence, extract just the inner content
    if "```" in text:
        # Find the first code block
        start = text.find("```")
        inner_start = text.index("\n", start) + 1
        end = text.rfind("```")
        if end > start:
            text = text[inner_start:end]
    # If model added preamble prose before the DOCTYPE, skip it
    doctype_idx = text.lower().find("<!doctype")
    html_idx    = text.lower().find("<html")
    first_tag   = min(i for i in [doctype_idx, html_idx] if i >= 0) if any(i >= 0 for i in [doctype_idx, html_idx]) else -1
    if first_tag > 0:
        text = text[first_tag:]
    return text.strip()


def _asset_fidelity_prefix(description: str, gamespec=None,
                            char_url: str = "", coll_url: str = "", obs_url: str = "") -> str:
    """Build a structured prompt prefix: GameSpec v2 block + PNG sprite + asset fidelity rules."""
    d = description.lower()

    def _abs_url(u: str) -> str:
        return u if u.startswith("http") else f"{BASE_URL}{u}"

    # GameSpec v2 block
    win_story = "You did it! Amazing!"
    gs_lines = ["GAMESPEC v2 (read this first — drives the entire game design):"]
    if gamespec:
        win_story = gamespec.get('win_story', win_story)
        gs_lines.append(f"- Archetype      : {gamespec.get('archetype','collector-adventure')}")
        gs_lines.append(f"- Player fantasy : {gamespec.get('player_fantasy','')}")
        gs_lines.append(f"- Main verb      : {gamespec.get('main_verb','collect')}")
        gs_lines.append(f"- Win story      : {win_story}")
        gs_lines.append(f"- Character      : {gamespec.get('character','')}")
        gs_lines.append(f"- Collectible    : {gamespec.get('collectible','')}")
        gs_lines.append(f"- Obstacle       : {gamespec.get('obstacle','')}")
        gs_lines.append(f"- World          : {gamespec.get('world','')}")
    else:
        gs_lines.append("- Archetype: collector-adventure (default)")
        gs_lines.append(f"- Win story      : {win_story}")
    gs_lines.append("")

    # JS constants — o3 must define these at the top of the script
    char_abs = _abs_url(char_url) if char_url else ""
    coll_abs = _abs_url(coll_url) if coll_url else ""
    obs_abs  = _abs_url(obs_url)  if obs_url  else ""
    gs_lines.append("DEFINE THESE JAVASCRIPT CONSTANTS AT THE TOP OF YOUR SCRIPT (before anything else):")
    if char_abs: gs_lines.append(f'  const CHAR_URL  = "{char_abs}";')
    if coll_abs: gs_lines.append(f'  const COLL_URL  = "{coll_abs}";')
    if obs_abs:  gs_lines.append(f'  const OBS_URL   = "{obs_abs}";')
    gs_lines.append(f'  const WIN_STORY = "{win_story}";')
    gs_lines.append("")

    # PNG sprite instructions — when sprites are provided, PROHIBIT geometry drawing
    sprite_lines = []
    if char_url or coll_url or obs_url:
        sprite_lines.append(
            "━━━ CRITICAL SPRITE ENFORCEMENT ━━━\n"
            "PNG sprites are provided below. For EACH object that has a sprite URL:\n"
            "  ✗ DO NOT render it using Canvas 2D API (no ctx.drawImage / ctx.fillRect)\n"
            "  ✗ DO NOT build it from THREE.js geometry (boxes, spheres, cones, etc.)\n"
            "  ✗ DO NOT substitute an emoji or colored rectangle\n"
            "  ✓ ONLY use createSpriteMesh(URL, w, h) as defined in the system prompt\n"
            "  ✓ This game MUST use Three.js r128 renderer — not a Canvas 2D game\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    if char_url:
        sprite_lines.append(
            f"CHARACTER PNG SPRITE — load via CHAR_URL constant:\n"
            f"  const hero = createSpriteMesh(CHAR_URL, 2.4, 2.4);\n"
            f"  Call billboardAll(camera, hero) every frame so it faces camera.\n"
            f"  Animate: gentle Y bob (+/- 0.06 * sin(t*3)). Squash scaleY 0.6→1 on land; stretch 1.4 on jump."
        )
    if coll_url:
        sprite_lines.append(
            f"COLLECTIBLE PNG SPRITE — load via COLL_URL constant:\n"
            f"  const m = createSpriteMesh(COLL_URL, 1.1, 1.1);\n"
            f"  Call billboardAll(camera, m) every frame. Spin Y-axis. Add PointLight child (warm gold)."
        )
    if obs_url:
        sprite_lines.append(
            f"OBSTACLE PNG SPRITE — load via OBS_URL constant:\n"
            f"  const m = createSpriteMesh(OBS_URL, 1.6, 1.6);\n"
            f"  Call billboardAll(camera, m) every frame. Random scale 0.9–1.4. Slight Y wobble."
        )
    if sprite_lines:
        sprite_lines.insert(0, "PNG SPRITES PROVIDED — use createSpriteMesh() for these objects (see system prompt for the function):")
        sprite_lines.append("")

    # Asset fidelity rules — only for objects that have NO PNG sprite
    rules = []
    if "unicorn" in d and not char_url:
        rules.append(
            "MUST implement createUnicorn(): rounded white horse body using SphereGeometry/ellipsoids, four legs with purple/gold hooves, neck, head, snout, blue/black eyes, ears, obvious gold cone horn, cyan/blue/purple mane, rainbow tail. Use separate THREE meshes for each body part; not a blob; do not use BoxGeometry for animal body/head."
        )
    if ("dragon" in d or "dragg" in d) and not char_url:
        rules.append(
            "MUST implement createDragon(): round emerald-green body (scaled SphereGeometry), head+snout, two bat-like wings (PlaneGeometry scaled to triangles), four short legs, two horns (ConeGeometry), tail with spikes. Eyes: glowing gold spheres. Scale body ~1.2x. Not a blob."
        )
    if ("bunny" in d or "rabbit" in d) and not char_url:
        rules.append(
            "MUST implement createBunny(): round white body (SphereGeometry), round head, two tall upright ears (CapsuleGeometry or cylinders), pink inner ears, black dot eyes, small pink nose, four short paws, fluffy cotton tail. Not a blob."
        )
    if ("cat" in d or "kitten" in d) and not char_url:
        rules.append(
            "MUST implement createCat(): orange tabby body, round head, two triangular ears with pink inner, bright green eyes, whiskers (thin cylinders), four paws with toes, long curved tail. Not a blob."
        )
    if ("robot" in d or "android" in d) and not char_url:
        rules.append(
            "MUST implement createRobot(): metallic boxy body (BoxGeometry with MeshStandardMaterial metalness:0.9), round head with antenna, glowing blue LED eyes, articulated arm/leg joints. Color scheme: silver+blue. Add subtle inner glow. Not plain rectangles."
        )
    if ("knight" in d or "warrior" in d or "hero" in d) and not char_url:
        rules.append(
            "MUST implement createKnight(): armored body with breastplate, helmet with visor, sword held in right hand, shield on left. Silver/gold materials with metalness. Multi-part with separate limbs."
        )
    if ("rock" in d or "rocks" in d or "boulder" in d) and not obs_url:
        rules.append(
            "MUST implement createRock(): clustered low-poly grey/brown DodecahedronGeometry/IcosahedronGeometry rocks with flatShading, lumpy non-uniform scales, darker facets, shadows; not bars/cubes."
        )
    if ("cloud" in d or "clouds" in d) and not obs_url:
        rules.append(
            "MUST implement createStormCloud(): 4–6 overlapping white/grey SphereGeometry puffs forming a cloud shape, with a grumpy face (sphere eyes, arc mouth), lightning bolt hanging below (yellow cylinder/cone). Not a flat box."
        )
    if ("spike" in d or "spikes" in d) and not obs_url:
        rules.append(
            "MUST implement createSpike(): cluster of 3–5 sharp purple/metal ConeGeometry spikes in a row, tips pointing up. Shiny metalness material. Not a bar."
        )
    if ("coin" in d or "coins" in d) and not coll_url:
        rules.append(
            "MUST implement createCoin(): flat gold CylinderGeometry (radius 0.3, height 0.08), metalness 0.8, spinning on Y-axis, warm PointLight child."
        )
    if ("gem" in d or "gems" in d or "crystal" in d) and not coll_url:
        rules.append(
            "MUST implement createGem(): OctahedronGeometry with iridescent purple/blue material, roughness 0.1, metalness 0.3, inner PointLight, Y-spin."
        )
    if ("star" in d or "stars" in d) and not coll_url:
        rules.append(
            "MUST implement createStarCollectible(): bright gold 3D spinning star mesh or cone/octahedron cluster with glow; do not use emoji for collectibles."
        )
    if "dragon" in d and ("rescue" in d or "save" in d or "free" in d):
        rules.append(
            "Archetype is FREE-FLIGHT-RESCUE: the dragon flies freely in 8 directions using arrow keys/WASD/touch. Rainbow/fire projectiles (space/tap) transform storm clouds into sunshine. Baby dragon eggs are the collectibles — rescue all of them to win. Show a clear goal counter 'X/10 baby dragons rescued'. Win screen: sparkle explosion + win_story text."
        )
    if not rules and not sprite_lines:
        rules.append(
            "MUST build all named characters, collectibles, and obstacles as recognizable multi-part THREE primitive models with distinct features. No vague blobs, no emoji substitutes, no plain bars or cubes."
        )

    gs_block = "\n".join(gs_lines)
    sprite_block = "\n".join(sprite_lines)
    rules_block = ("ASSET FIDELITY AND ART DIRECTION REQUIREMENTS:\n" + "\n".join(f"- {r}" for r in rules)) if rules else ""
    parts = [p for p in [gs_block, sprite_block, rules_block] if p.strip()]
    return "\n".join(parts) + "\n\nCHILD GAME DESCRIPTION:\n"

@app.post("/generate-threejs-game")
async def generate_threejs_game(req: GenerateThreeJSRequest):
    try:
        # Unicorn template fallback: only used when no PNG sprite URL is supplied.
        # If char_url is provided, let o3 generate the game using the PNG billboard.
        if "unicorn" in req.description.lower() and not req.char_url:
            session_id = req.session_id or str(uuid.uuid4())[:8]
            title_match = re.match(r"\s*([^:.!\n]{3,60})", req.description)
            game_name = (title_match.group(1).strip() if title_match else "Unicorn Fun 3D")
            game_name = re.sub(r"\s+", " ", game_name)[:50]
            safe_name = re.sub(r"[^a-z0-9_]", "_", game_name.lower())[:30]
            filename = f"{safe_name}_{session_id}_3d.html"
            shell = (BASE_DIR / "templates" / "unicorn_reference_3d.html").read_text(encoding="utf-8")
            html = shell.replace("{{GAME_NAME}}", game_name)
            (GAMES_DIR / filename).write_text(html, encoding="utf-8")
            return {
                "ok": True,
                "game_url": f"{BASE_URL}/games/{filename}",
                "filename": filename,
                "model": "template/unicorn_reference_3d",
                "tokens": 0,
            }

        response = await client.chat.completions.create(
            model=MODEL_CODE,
            messages=[
                {"role": "system", "content": _load_system_prompt()},
                {"role": "user",   "content": _asset_fidelity_prefix(
                    req.description,
                    req.gamespec or None,
                    req.char_url, req.coll_url, req.obs_url,
                ) + req.description},
            ],
            max_completion_tokens=9000,
        )
        html = _strip_fences(response.choices[0].message.content)

        if not html.startswith("<!DOCTYPE") and not html.startswith("<html"):
            return {"ok": False, "error": "Model returned non-HTML output"}

        session_id = req.session_id or str(uuid.uuid4())[:8]
        safe_name  = re.sub(r"[^a-z0-9_]", "_", req.description.lower())[:30]
        filename   = f"{safe_name}_{session_id}_3d.html"
        (GAMES_DIR / filename).write_text(html, encoding="utf-8")

        return {
            "ok":       True,
            "game_url": f"{BASE_URL}/games/{filename}",
            "filename": filename,
            "model":    response.model,
            "tokens":   response.usage.total_tokens,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Game Designer Review Agent ────────────────────────────────────────────────

GAME_REVIEW_PROMPT = """You are Maya, a Senior Game Designer at a top children's game studio
(think Toca Boca, Nickelodeon, PBS Kids). You have shipped 30+ kids games played by millions
of children aged 4–8. You review AI-generated browser games with a sharp, practical eye.

Your job: read the full HTML/JavaScript game code, then produce a thorough review from a
game designer's perspective. You are both a critic and a fixer — every issue must come with
a concrete fix_hint so a developer can act on it immediately.

## Your Review Framework

### 1. First 5 Seconds (First Impression)
- Does the game load and show something beautiful immediately?
- Is the character visible and charming from the first frame?
- Is there a clear "tap to start" prompt?

### 2. Core Game Feel (The Most Important Thing)
- Does jumping feel snappy and satisfying? (should respond in <2 frames)
- Is there audio feedback on every action?
- Do collectibles feel rewarding to grab?
- Do obstacles feel fair and readable (not surprise-kills)?

### 3. Child-First Design (ages 4–8)
- Can a 4-year-old succeed in the first 30 seconds?
- Is there a safe warm-up zone with no obstacles?
- Are hitboxes forgiving (40% smaller than visual)?
- Is there 2+ seconds of invincibility after a hit?
- Are there enough lives (5+)?

### 4. Clarity & Polish
- Can you tell at a glance what to collect vs. what to avoid?
- Is the HUD readable (large text, high contrast)?
- Is the win condition clearly communicated?
- Is the win screen celebratory and rewarding?

### 5. Code Bugs That Break Gameplay
- Objects never appearing (visible never reset to true)
- Collision flags not reset between spawns (hit/collected stuck as true)
- Square hitbox instead of circular distance check
- Particle bursts creating separate requestAnimationFrame loops
- End screen stacking (old screen not removed before new)
- Audio context not resumed (silence)
- Delta time not capped (game explodes on tab switch)

## Output Format

Return ONLY valid JSON — no prose, no markdown fences. Use this exact schema:

{
  "reviewer": "Maya",
  "score": <integer 1-10>,
  "headline": "<one sentence verdict>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "issues": [
    {
      "id": "issue_1",
      "severity": "critical|high|medium|low",
      "category": "bug|game_feel|child_design|clarity|polish",
      "title": "<short title>",
      "description": "<what is wrong and why it matters>",
      "fix_hint": "<concrete code-level fix, specific enough to implement>"
    }
  ],
  "fix_summary": "<2-sentence description of the most important things to fix>"
}

Severity guide:
- critical: game is broken or unplayable because of this
- high: seriously hurts fun or fairness for a child
- medium: noticeably reduces quality
- low: nice to have polish

Be thorough. Find at least 3 issues and at most 12. Be specific — vague feedback is useless."""


GAME_FIX_PROMPT = """You are an expert children's game developer. You will receive:
1. The original game HTML/JavaScript
2. A list of issues identified by a game designer reviewer

Your job: fix EVERY issue listed. Return the complete fixed HTML file.

Rules:
- Fix all listed issues, in order of severity (critical first)
- Do NOT change visual style, game concept, or character — only fix the issues
- Do NOT add new features beyond what the fixes require
- Keep the same game mechanics and structure
- After fixing bugs, add these if missing: coyote time jump, burst particles in main loop,
  circular collision, invincibility flash, end screen cleanup, audio try/catch wrapper
- Return ONLY the complete HTML — no explanation, no markdown fences"""


class ReviewGameRequest(BaseModel):
    game_html: str
    game_name: str = ""
    session_id: str = ""

class FixGameRequest(BaseModel):
    game_html: str
    issues: list = []
    fix_summary: str = ""
    game_name: str = ""
    session_id: str = ""


@app.post("/review-game")
async def review_game(req: ReviewGameRequest):
    try:
        # Truncate very large games to fit context — keep first 12000 chars (covers all game logic)
        html_excerpt = req.game_html[:12000]
        if len(req.game_html) > 12000:
            html_excerpt += "\n\n[... truncated for review ...]"

        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": GAME_REVIEW_PROMPT},
                {"role": "user", "content":
                    f"Game name: {req.game_name or 'Untitled'}\n\n"
                    f"Full game code:\n```html\n{html_excerpt}\n```"},
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.3,
        )
        review = json.loads(response.choices[0].message.content)
        return {"ok": True, "review": review}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/fix-game")
async def fix_game(req: FixGameRequest):
    try:
        issues_text = "\n".join(
            f"[{i['severity'].upper()}] {i['title']}: {i['description']}\nFix: {i['fix_hint']}"
            for i in req.issues
        )
        user_msg = (
            f"Game name: {req.game_name or 'Untitled'}\n\n"
            f"ISSUES TO FIX:\n{issues_text}\n\n"
            f"OVERALL FIX SUMMARY: {req.fix_summary}\n\n"
            f"ORIGINAL GAME HTML:\n{req.game_html}"
        )
        response = await client.chat.completions.create(
            model=MODEL_CODE,
            messages=[
                {"role": "system", "content": GAME_FIX_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_completion_tokens=12000,
        )
        html = _strip_fences(response.choices[0].message.content)
        if not html.startswith("<!DOCTYPE") and not html.startswith("<html"):
            return {"ok": False, "error": "Model returned non-HTML"}

        session_id = req.session_id or str(uuid.uuid4())[:8]
        safe_name  = re.sub(r"[^a-z0-9_]", "_", (req.game_name or "fixed").lower())[:28]
        filename   = f"{safe_name}_{session_id}_fixed.html"
        (GAMES_DIR / filename).write_text(html, encoding="utf-8")
        return {
            "ok": True,
            "game_url": f"{BASE_URL}/games/{filename}",
            "filename": filename,
            "tokens": response.usage.total_tokens,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
