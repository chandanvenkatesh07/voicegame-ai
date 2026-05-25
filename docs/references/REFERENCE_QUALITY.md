# Visual Quality Reference

All generated games must match this visual quality bar.

## Target Style: Polished 16-bit Pixel-Art Platformer

The reference images below show the exact level of visual quality we target.
Every character, collectible, obstacle, and background element must be:

- **Immediately recognizable** — a child aged 4–8 must know what it is on first glance
- **Crisp and large** — no tiny unreadable sprites
- **Vibrant and saturated** — candy-bright colors, no grey or muted tones
- **Charming** — characters have personality (eyes, expressions, poses)

## Reference Images

Place your reference screenshots here. Suggested filenames:

| File | Description |
|------|-------------|
| `reference_knight_castle.png` | Knight character, coins, green slime, castle background — Mario-style pixel art platformer |
| `reference_level_up.png` | Level Up screen with boy character, coins, butterfly, heart HUD — polished pixel art |

> **To add references**: Save the reference screenshots to this folder as PNG files.
> They will automatically be referenced in the README.

## Quality Checklist

Use this checklist when evaluating a generated game:

### Characters
- [ ] Character sprite is large (≥15% of screen height)
- [ ] Character has a recognizable silhouette (not a blob or rectangle)
- [ ] Character has eyes/expression (personality)
- [ ] Character animates (squash/stretch on jump/land)

### Collectibles
- [ ] Collectible sprites are visible and recognizable (coin = round gold, star = star shape)
- [ ] Collectibles spin or glow
- [ ] Collecting triggers a satisfying effect (sparkle burst + sound)

### Background
- [ ] At least 3 depth layers (sky, midground, ground)
- [ ] World theme is clearly readable (forest ≠ space ≠ candy land)
- [ ] Parallax scrolling (different layers move at different speeds)

### HUD
- [ ] Score is large and readable
- [ ] Lives/hearts are clear icons (not text "lives: 3")
- [ ] Tutorial hint shown at game start

### Game Feel (Juice)
- [ ] Screen shake on hit
- [ ] Particle burst on collect
- [ ] Squash on land
- [ ] Sound on every action

## Bad Examples (What to Avoid)

- ❌ Robot character drawn as plain rectangles
- ❌ Dragon character as a stick figure or flat 2D blob
- ❌ Collectibles as small colored squares
- ❌ Grey or muted color palette
- ❌ Flat single-layer background
- ❌ Emoji used as game objects
- ❌ Characters smaller than a fingertip on screen
