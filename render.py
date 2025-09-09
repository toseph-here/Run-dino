from PIL import Image, ImageDraw, ImageFont
from flask import Flask

FONT = None
try:
    FONT = ImageFont.truetype("arial.ttf", 14)
except:
    FONT = ImageFont.load_default()

def render_frame(states, tick, scores, obstacles, track_width=800, track_height=200):
    w = track_width
    h = track_height
    img = Image.new("RGB", (w, h+60), (28,28,30))
    d = ImageDraw.Draw(img)

    # ground
    d.rectangle([0, h-10, w, h], fill=(200,200,200))
    # moon
    d.ellipse([w-120, 10, w-80,50], fill=(200,200,200))

    # obstacles
    for o in obstacles:
        x = int(o.x/(1200/700))
        d.rectangle([x, h-30-o.h, x+o.w, h-10], fill=(50,200,50))

    # dinos
    colors = [(180,180,180),(160,200,160),(160,160,200)]
    for i, s in enumerate(states):
        x = s['x']
        y = int(h-30 - s.get('y',0))
        col = colors[i%len(colors)]
        if not s.get('alive', True):
            col = (100,100,100)
        d.rectangle([x, y, x+24, y+20], fill=col, outline=(0,0,0))
        d.ellipse([x+18,y+3,x+21,y+6], fill=(0,0,0))

    # scoreboard
    d.text((8,8), f"TICK: {tick}", font=FONT, fill=(220,220,220))
    for i in range(len(states)):
        d.text((8,30 + i*14), f"P{i+1}: {scores.get(i,0)}", font=FONT, fill=(220,220,220))

    return img


# ----------------------------
# Flask app for Render hosting
# ----------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running with Render!"
