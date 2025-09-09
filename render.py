# render.py
from PIL import Image, ImageDraw, ImageFont

try:
    FONT = ImageFont.truetype("arial.ttf", 14)
    SMALL = ImageFont.truetype("arial.ttf", 12)
except:
    from PIL import ImageFont
    FONT = ImageFont.load_default()
    SMALL = ImageFont.load_default()

# simple colors for players
PLAYER_COLORS = [(200,200,200), (160,200,160), (160,160,220)]
BG = (28,28,30)
GROUND = (210,210,210)

def render_frame(states, obstacles, tick, finish_x,
                 track_w=1000, track_h=220):
    """
    states: list of dicts: {'x': float (world x), 'y': float (vertical, negative when jumping), 'alive':bool, 'username':str}
    obstacles: list of dicts: {'x': float (world x), 'w':int, 'h':int}
    finish_x: int (world finish line)
    """
    margin_left = 60
    margin_right = 40
    w = track_w
    h = track_h
    img = Image.new("RGB", (w, h+70), BG)
    draw = ImageDraw.Draw(img)

    # ground
    draw.rectangle([0, h-20, w, h+70], fill=BG)
    draw.line([0, h-10, w, h-10], fill=GROUND, width=3)

    # scale world -> screen
    usable = w - margin_left - margin_right
    scale = max(0.001, usable / max(finish_x, 1))

    # draw finish line
    fx = margin_left + int(finish_x * scale)
    draw.line([fx, 10, fx, h-10], fill=(255,215,0), width=3)
    draw.text((fx-30, 12), "FINISH", font=SMALL, fill=(255,215,0))

    # draw obstacles
    for o in obstacles:
        ox = margin_left + int(o['x'] * scale)
        oy = h-10 - o['h']
        # cactus body
        draw.rectangle([ox, oy, ox + o['w'], h-12], fill=(120,180,120), outline=(20,20,20))
        # small arm to make it look cactus-y
        draw.rectangle([ox - 3, oy + 6, ox + 6, oy + 12], fill=(120,180,120), outline=(20,20,20))

    # draw players in lanes (stacked vertically)
    lane_y_base = h - 40
    lane_spacing = 40
    for i, s in enumerate(states):
        color = PLAYER_COLORS[i % len(PLAYER_COLORS)]
        sx = margin_left + int(s['x'] * scale)
        sy = lane_y_base - i*lane_spacing - (s.get('y', 0))  # s.y is negative when jumping
        # body
        box = [sx, sy-18, sx+28, sy]
        fill = color if s.get('alive', True) else (100,100,100)
        draw.rectangle(box, fill=fill, outline=(0,0,0))
        # head (small)
        draw.rectangle([sx+20, sy-22, sx+28, sy-16], fill=fill, outline=(0,0,0))
        # eye
        draw.ellipse([sx+22, sy-20, sx+24, sy-18], fill=(0,0,0))
        # username and score
        name = s.get('username', f"P{i+1}")
        score = s.get('score', 0)
        status = "" if s.get('alive', True) else " (DEAD)"
        draw.text((8, 12 + i*14), f"{i+1}. {name} — {score}{status}", font=SMALL, fill=(230,230,230))

    # top-left: tick
    draw.text((8, h-50), f"TICK: {tick}", font=FONT, fill=(220,220,220))

    return img
