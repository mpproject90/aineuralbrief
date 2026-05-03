#!/usr/bin/env python3
"""AI Neural Brief — Daily Instagram content generator"""

import os, io, json, random, textwrap, requests, feedparser
from datetime import datetime, timezone, timedelta
from time import mktime
from PIL import Image, ImageDraw, ImageFont
import anthropic

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BOT_TOKEN         = os.environ["BOT_TOKEN"]
CHAT_ID           = os.environ["CHAT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
POSTS_PER_RUN     = int(os.environ.get("POSTS_COUNT", "4"))

# ─── PALETTE ─────────────────────────────────────────────────────────────────
BG     = (13, 15, 20)
CARD   = (22, 27, 40)
ACCENT = (79, 142, 247)
ORANGE = (232, 123, 74)
WHITE  = (255, 255, 255)
GREY   = (140, 150, 170)
CREAM  = (248, 245, 238)
DARK   = (26, 26, 46)
W, H   = 1080, 1080

# ─── NEWS SOURCES ────────────────────────────────────────────────────────────
SOURCES = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.technologyreview.com/feed/",
    "https://news.google.com/rss/search?q=artificial+intelligence+news&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=humanoid+robot&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=ChatGPT+OR+Claude+OR+Gemini+update&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=OpenAI+OR+Anthropic+OR+DeepMind&hl=en-US&gl=US&ceid=US:en",
]

SYSTEM_PROMPT = """You are the content strategist for @aineuralbrief, an Instagram page covering AI and humanoid robotics news.

Transform a news headline into a dense, valuable Instagram infographic post.
Make every point specific and insightful — not generic. Each point should teach something real.

Output ONLY valid JSON, no markdown, no code fences:
{
  "hook_title": "PUNCHY TITLE IN CAPS, max 6 words",
  "subtitle": "One line context, max 10 words",
  "category": "one of exactly: 🤖 AI Models | 🦾 Humanoid Robots | 🧠 AI Research | 💼 AI Business | ⚡ AI Tools",
  "points": ["point 1 max 10 words", "point 2", "point 3", "point 4", "point 5", "point 6"],
  "caption": "3-4 line Instagram caption with emoji. End with: Comment BRIEF → I'll DM you this week's full AI roundup 📩",
  "hashtags": "#AI #ArtificialIntelligence #AINews #NeuralBrief #MachineLearning #AITools #FutureOfAI #TechNews #Robotics #Innovation"
}"""


# ─── FETCH ───────────────────────────────────────────────────────────────────

def fetch_articles():
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    for url in SOURCES:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "NeuralBriefBot/1.0"})
            for entry in feed.entries[:6]:
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))[:400]
                pub     = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub:
                    from time import mktime as _mk
                    if datetime.fromtimestamp(_mk(pub), tz=timezone.utc) < cutoff:
                        continue
                if title and len(title) > 20:
                    articles.append({"title": title, "summary": summary, "source": feed.feed.get("title", "")})
        except Exception as e:
            print(f"  Source error: {e}")
    seen, unique = [], []
    for a in articles:
        key = a["title"][:40].lower()
        if not any(key in s or s in key for s in seen):
            seen.append(key)
            unique.append(a)
    random.shuffle(unique)
    return unique[:20]


# ─── GENERATE ────────────────────────────────────────────────────────────────

def generate_content(article, client):
    prompt   = f"Article: {article['title']}\nContext: {article['summary'][:300]}"
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=900,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.split("```")[0]
    return json.loads(text.strip())


# ─── FONT & DRAW HELPERS ─────────────────────────────────────────────────────

def get_fonts():
    bold_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    reg_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    bold = next((p for p in bold_paths if os.path.exists(p)), None)
    reg  = next((p for p in reg_paths  if os.path.exists(p)), None)
    return bold, reg

def f(path, size):
    try:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    return ImageFont.load_default()

def rr(draw, xy, r, fill):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1+r, y1, x2-r, y2], fill=fill)
    draw.rectangle([x1, y1+r, x2, y2-r], fill=fill)
    for cx, cy in [(x1,y1),(x2-r*2,y1),(x1,y2-r*2),(x2-r*2,y2-r*2)]:
        draw.ellipse([cx, cy, cx+r*2, cy+r*2], fill=fill)

def badge(draw, cx, cy, n, font, bg, fg, size=40):
    r = size // 2
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=bg)
    t  = str(n)
    bb = draw.textbbox((0, 0), t, font=font)
    draw.text((cx-(bb[2]-bb[0])//2 - bb[0], cy-(bb[3]-bb[1])//2 - bb[1]), t, font=font, fill=fg)

def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textbbox((0,0), test, font=font)[2] > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines

def title_block(draw, text, y, bold_path, color=WHITE, max_w=960, pad=60):
    sz   = 64 if len(text) < 28 else (52 if len(text) < 42 else 42)
    font = f(bold_path, sz)
    for line in wrap(draw, text, font, max_w)[:3]:
        draw.text((pad, y), line, font=font, fill=color)
        bb = draw.textbbox((0,0), line, font=font)
        y += bb[3]-bb[1]+6
    return y

def footer_dark(draw, reg, bold):
    draw.rectangle([0, H-78, W, H], fill=CARD)
    draw.text((60, H-52), "@aineuralbrief", font=f(bold, 26), fill=ACCENT)
    wm = "aineuralbrief.com"
    bb = draw.textbbox((0,0), wm, font=f(reg, 24))
    draw.text((W-60-(bb[2]-bb[0]), H-52), wm, font=f(reg, 24), fill=GREY)

def done(img):
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf


# ─── TEMPLATE 1: DARK BULLETS ────────────────────────────────────────────────
# Dark navy bg, blue header, diamond bullet points

def render_dark_bullets(content):
    bold, reg = get_fonts()
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    PAD  = 60

    draw.rectangle([0, 0, W, 88], fill=ACCENT)
    draw.text((PAD, 24), "◆  AI NEURAL BRIEF", font=f(bold, 38), fill=WHITE)
    ds = datetime.now().strftime("%b %d, %Y")
    bb = draw.textbbox((0,0), ds, font=f(reg, 26))
    draw.text((W-PAD-(bb[2]-bb[0]), 30), ds, font=f(reg, 26), fill=WHITE)

    y = 108
    cat = content.get("category", "🤖 AI Models")
    cb  = draw.textbbox((0,0), cat, font=f(reg, 24))
    rr(draw, (PAD, y, PAD+cb[2]-cb[0]+32, y+36), 8, CARD)
    draw.text((PAD+16, y+6), cat, font=f(reg, 24), fill=ACCENT)
    y += 54

    y = title_block(draw, content.get("hook_title","AI UPDATE").upper(), y, bold)
    sub = content.get("subtitle", "")
    if sub:
        draw.text((PAD, y+4), sub, font=f(reg, 28), fill=GREY)
        bb = draw.textbbox((0,0), sub, font=f(reg, 28))
        y += bb[3]-bb[1]+20
    draw.rectangle([PAD, y+6, PAD+90, y+10], fill=ACCENT)
    y += 26

    points = content.get("points", [])[:6]
    row_h  = min(72, max(48, (H-88-y-10) // max(len(points),1)))
    for pt in points:
        if y > H-110: break
        bx, by = PAD, y+10
        draw.polygon([(bx+10,by),(bx+20,by+10),(bx+10,by+20),(bx,by+10)], fill=ACCENT)
        draw.text((PAD+34, y+2), pt, font=f(reg, 27), fill=WHITE)
        y += row_h

    footer_dark(draw, reg, bold)
    return done(img)


# ─── TEMPLATE 2: LIGHT NUMBERED LIST ─────────────────────────────────────────
# Cream background, numbered circles, dark text — similar to rubenhassid clean posts

def render_light_numbered(content):
    bold, reg = get_fonts()
    img  = Image.new("RGB", (W, H), CREAM)
    draw = ImageDraw.Draw(img)
    PAD  = 60

    draw.rectangle([0, 0, W, 8], fill=ACCENT)

    y = 36
    cat = content.get("category", "🤖 AI Models")[:22]
    cb  = draw.textbbox((0,0), cat, font=f(reg, 22))
    rr(draw, (PAD, y, PAD+cb[2]-cb[0]+28, y+34), 8, ACCENT)
    draw.text((PAD+14, y+6), cat, font=f(reg, 22), fill=WHITE)
    y += 52

    y = title_block(draw, content.get("hook_title","AI UPDATE").upper(), y, bold, color=DARK)
    sub = content.get("subtitle", "")
    if sub:
        draw.text((PAD, y+2), sub, font=f(reg, 28), fill=(100,100,120))
        bb = draw.textbbox((0,0), sub, font=f(reg, 28))
        y += bb[3]-bb[1]+14
    draw.rectangle([PAD, y+6, W-PAD, y+3], fill=ACCENT)
    y += 26

    points = content.get("points", [])[:6]
    row_h  = min(84, max(52, (H-72-y) // max(len(points),1)))
    f_num  = f(bold, 26)
    f_pt   = f(reg, 27)
    for i, pt in enumerate(points, 1):
        if y > H-100: break
        badge(draw, PAD+22, y+22, i, f_num, ACCENT, WHITE, size=40)
        lines = wrap(draw, pt, f_pt, W-PAD-68-PAD)
        ty = y + max(0, (40-len(lines)*32)//2)
        for ln in lines[:2]:
            draw.text((PAD+58, ty), ln, font=f_pt, fill=DARK)
            bb = draw.textbbox((0,0), ln, font=f_pt)
            ty += bb[3]-bb[1]+4
        y += row_h

    draw.rectangle([0, H-72, W, H], fill=(225, 220, 212))
    draw.text((PAD, H-48), "@aineuralbrief", font=f(bold, 26), fill=ACCENT)
    wm = "aineuralbrief.com"
    bb = draw.textbbox((0,0), wm, font=f(reg, 24))
    draw.text((W-PAD-(bb[2]-bb[0]), H-48), wm, font=f(reg, 24), fill=(110,105,95))
    return done(img)


# ─── TEMPLATE 3: DARK CARD GRID ──────────────────────────────────────────────
# 2×3 grid of numbered cards — like rubenhassid checklist format

def render_card_grid(content):
    bold, reg = get_fonts()
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    PAD  = 50

    draw.rectangle([0, 0, W, 88], fill=ACCENT)
    draw.text((PAD, 24), "◆  AI NEURAL BRIEF", font=f(bold, 38), fill=WHITE)

    y = 100
    y = title_block(draw, content.get("hook_title","AI UPDATE").upper(), y, bold, max_w=W-PAD*2, pad=PAD)
    sub = content.get("subtitle", "")
    if sub:
        draw.text((PAD, y), sub, font=f(reg, 26), fill=GREY)
        bb = draw.textbbox((0,0), sub, font=f(reg, 26))
        y += bb[3]-bb[1]+10
    y += 10

    points = content.get("points", [])[:6]
    GAP   = 16
    COL_W = (W - PAD*2 - GAP) // 2
    avail = H - 88 - y - 10
    ROW_H = (avail - GAP*2) // 3

    f_num = f(bold, 26)
    f_txt = f(reg, 24)
    for i, pt in enumerate(points):
        col = i % 2
        row = i // 2
        x1  = PAD + col*(COL_W+GAP)
        y1  = y   + row*(ROW_H+GAP)
        rr(draw, (x1, y1, x1+COL_W, y1+ROW_H), 12, CARD)
        badge(draw, x1+24, y1+26, i+1, f_num, ACCENT, WHITE, size=36)
        lines = wrap(draw, pt, f_txt, COL_W-28)
        ty = y1 + 54
        for ln in lines[:3]:
            draw.text((x1+12, ty), ln, font=f_txt, fill=WHITE)
            bb = draw.textbbox((0,0), ln, font=f_txt)
            ty += bb[3]-bb[1]+4

    footer_dark(draw, reg, bold)
    return done(img)


# ─── TEMPLATE 4: STEPS FLOW ──────────────────────────────────────────────────
# Numbered steps with connecting vertical line — orange accent for variety

def render_steps_flow(content):
    bold, reg = get_fonts()
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    PAD  = 60

    draw.rectangle([0, 0, W, 88], fill=ORANGE)
    draw.text((PAD, 24), "◆  AI NEURAL BRIEF", font=f(bold, 38), fill=WHITE)

    y = 104
    y = title_block(draw, content.get("hook_title","AI UPDATE").upper(), y, bold)
    sub = content.get("subtitle", "")
    if sub:
        draw.text((PAD, y), sub, font=f(reg, 26), fill=GREY)
        bb = draw.textbbox((0,0), sub, font=f(reg, 26))
        y += bb[3]-bb[1]+12
    y += 8

    points = content.get("points", [])[:6]
    avail = H - 88 - y - 10
    ROW_H = min(104, max(62, avail // max(len(points),1)))

    BX    = PAD + 26
    TX    = PAD + 76
    f_num = f(bold, 26)
    f_txt = f(reg, 27)

    for i, pt in enumerate(points):
        if y > H-100: break
        cy = y + ROW_H//2
        if i < len(points)-1:
            draw.line([BX, cy+26, BX, cy+ROW_H], fill=ORANGE, width=3)
        badge(draw, BX, cy, i+1, f_num, ORANGE, WHITE, size=42)
        lines = wrap(draw, pt, f_txt, W-TX-PAD)
        th    = len(lines)*34
        ty    = cy - th//2
        for ln in lines[:2]:
            draw.text((TX, ty), ln, font=f_txt, fill=WHITE)
            bb = draw.textbbox((0,0), ln, font=f_txt)
            ty += bb[3]-bb[1]+4
        y += ROW_H

    footer_dark(draw, reg, bold)
    return done(img)


# ─── RENDER DISPATCHER ───────────────────────────────────────────────────────

TEMPLATES = [render_dark_bullets, render_light_numbered, render_card_grid, render_steps_flow]

def render_image(content):
    return random.choice(TEMPLATES)(content)


# ─── TELEGRAM ────────────────────────────────────────────────────────────────

def send_telegram(image_buf, caption):
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    resp = requests.post(
        url,
        data={"chat_id": CHAT_ID, "caption": caption[:1024]},
        files={"photo": ("post.jpg", image_buf, "image/jpeg")},
        timeout=30,
    )
    resp.raise_for_status()
    print(f"  Sent → message_id {resp.json()['result']['message_id']}")


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().isoformat()}] AI Neural Brief — generating {POSTS_PER_RUN} post(s)")
    client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    articles = fetch_articles()
    print(f"  Fetched {len(articles)} articles")
    if not articles:
        print("  No articles found, exiting")
        return
    step     = max(1, len(articles) // POSTS_PER_RUN)
    selected = articles[::step][:POSTS_PER_RUN]
    for i, article in enumerate(selected, 1):
        print(f"  [{i}/{len(selected)}] {article['title'][:70]}")
        try:
            content   = generate_content(article, client)
            image_buf = render_image(content)
            caption   = content.get("caption", "") + "\n\n" + content.get("hashtags", "")
            send_telegram(image_buf, caption)
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            import traceback
            traceback.print_exc()
    print("  Done.")


if __name__ == "__main__":
    main()
