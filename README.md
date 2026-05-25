# ✨ Sparkle's Magic Game Maker

A voice-powered game creation app for kids aged 4–8. An animated fairy named Sparkle talks with kids through their microphone, collects their game ideas, and uses AI to generate a playable HTML5 game — right on the MacBook.

## Quick Start

### 1. Get an OpenAI API key
Go to https://platform.openai.com/api-keys and create a key.

### 2. Add your key
```bash
cp .env.example .env
# Edit .env and paste your key after OPENAI_API_KEY=
```

### 3. Run
```bash
./start.sh
```
The browser opens automatically at http://localhost:8000

---

## How it works

```
Kid talks (mic) → Web Speech API (free, in-browser) → Server → GPT-4o
GPT-4o replies → Server → Browser speaks reply (Speech Synthesis, free)
... back and forth 6 questions ...
GPT-4o generates complete HTML5 game → Saved to /games/
Kid clicks PLAY → Game opens in new tab
```

## Controls in generated games
- **Arrow keys**: move left/right (and sometimes up to jump)
- **Spacebar**: jump / fly

## What Sparkle asks kids
1. What kind of game? (jumping / flying / catching)
2. Who is the player? (unicorn, bunny, dragon, cat, star...)
3. What world? (forest, space, candy land, ocean...)
4. What do you collect? (stars, coins, hearts...)
5. What do you avoid? (rocks, spiky things, clouds...)
6. What's your game called?

## File structure
```
fairy-game-maker/
├── server.py          — FastAPI backend
├── start.sh           — One-click launcher
├── frontend/
│   ├── index.html     — Fairy UI
│   ├── fairy.css      — Animations
│   └── fairy.js       — Voice + chat + game launch
├── assets/
│   ├── fairy.svg      — Sparkle the fairy
│   ├── characters/    — unicorn, bunny, dragon, cat, star
│   ├── obstacles/     — rock, cloud, spike, cactus
│   └── collectibles/  — coin, gem, star, heart
└── games/             — Generated games saved here
```

## Visual Quality Target

All generated games must match the visual quality of a **bright storybook cartoon runner** —
large PNG sprite characters, warm saturated palette, crisp cartoon backgrounds.
Think: Kirby's Dream Land or PaperMario — flat, charming, immediately readable.

### Reference screenshots

| Example 1 — Knight Platformer | Example 2 — Level Up Screen |
|---|---|
| ![Knight pixel art platformer](docs/references/reference_knight_castle.png) | ![Level up pixel art](docs/references/reference_level_up.png) |

> Save your reference screenshots to `docs/references/` with the filenames above.
> See [`docs/references/REFERENCE_QUALITY.md`](docs/references/REFERENCE_QUALITY.md) for the full quality checklist.

### What "quality" means

- **Characters**: Large, crisp sprite with personality — immediately recognizable silhouette
- **Collectibles**: Iconic shapes (round gold coin, 5-point star, diamond gem) — NOT colored squares
- **Background**: 3+ depth layers with parallax, world theme immediately readable
- **HUD**: Bold large icons (❤️❤️❤️ not "lives: 3"), high-contrast score display
- **Juice**: Camera shake on hit, YAY popup + icon-fly on collect, dust puff + squash/stretch on jump
- **Start**: "Sparkle made this just for you!" ceremony screen
- **End**: Accomplishment-focused — "You collected X ⭐ — Sparkle is so proud!"

### What to avoid

| ❌ Bad | ✅ Good |
|--------|---------|
| Robot as plain grey rectangles | Robot as DALL-E sprite or detailed geometry |
| Dragon as flat stick figure | Dragon using the pre-generated Pixar sprite |
| Collectibles as tiny colored squares | Spinning coin/star sprites with glow |
| Single flat background color | 3-layer parallax sky + hills + ground |
| Emoji used as game objects | Proper sprite billboards |

### Regenerating assets (pixel-art style)

The sprite assets in `assets/` were generated with DALL-E. To regenerate with updated prompts:

```bash
# Delete old assets first (they're cached by filename)
rm assets/characters/*.png assets/collectibles/*.png assets/obstacles/*.png

# Regenerate (costs ~$0.60, ~15 images at $0.04 each)
python generate_assets.py
```

---

## Cost estimate
- ~$0.05–0.20 per complete game session (conversation + generation)
- Use `OPENAI_MODEL=gpt-4o-mini` in .env to cut costs ~10x (slightly simpler games)

## Voice requirements
- **Chrome** or **Safari** for microphone (Web Speech API)
- Kids can also type if preferred
- No audio API key needed — browser handles voice for free
