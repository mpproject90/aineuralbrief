#!/usr/bin/env python3
"""AI Neural Brief — Daily Instagram content generator"""

import os, io, json, random, requests, feedparser
from datetime import datetime, timezone, timedelta
from time import mktime
from PIL import Image, ImageDraw, ImageFont
import anthropic
from github import Github

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BOT_TOKEN         = os.environ["BOT_TOKEN"]
CHAT_ID           = os.environ["CHAT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN      = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO       = "mpproject90/aineuralbrief"
POSTS_PER_RUN     = int(os.environ.get("POSTS_COUNT", "4"))
NUM_TEMPLATES     = 5

# ─── PALETTE ─────────────────────────────────────────────────────────────────
BG     = (13, 15, 20)
CARD   = (22, 27, 40)
CARD2  = (30, 36, 54)
ACCENT = (79, 142, 247)
ORANGE = (232, 123, 74)
GREEN  = (72, 199, 142)
PURPLE = (162, 106, 245)
WHITE  = (255, 255, 255)
GREY   = (140, 150, 170)
CREAM  = (248, 245, 238)
DARK   = (26, 26, 46)
W, H   = 1080, 1080
PAD    = 58

BASE = """You are the content strategist for @aineuralbrief, an Instagram page covering AI and humanoid robotics news.
Transform a news headline into a dense, valuable infographic. Be specific — not generic. Teach something real.
Output ONLY valid JSON, no markdown fences. caption must end with: Comment BRIEF → I'll DM you this week's full AI roundup 📩
hashtags: #AI #ArtificialIntelligence #AINews #NeuralBrief #MachineLearning #AITools #FutureOfAI #TechNews #Robotics #Innovation"""

SYSTEM_PROMPTS = [

# T0 — Dark Bullets: 6 sharp news insights
BASE + """

JSON format:
{
  "hook_title": "PUNCHY CAPS TITLE max 6 words",
  "subtitle": "one line context max 10 words",
  "category": "AI Models | Humanoid Robots | AI Research | AI Business | AI Tools",
  "points": ["insight 1 max 10 words", "insight 2", "insight 3", "insight 4", "insight 5", "insight 6"],
  "caption": "3-4 lines with emoji",
  "hashtags": "..."
}""",

# T1 — Comparison: frame as natural contrast (before/after, old/new, without/with AI, etc)
BASE + """

Find the most compelling contrast angle for this news (e.g. old model vs new model, manual vs AI-powered, before vs after).
Choose column labels that make the contrast clear and punchy.

JSON format:
{
  "hook_title": "PUNCHY CAPS TITLE max 6 words",
  "subtitle": "one line context max 10 words",
  "left_title": "LEFT LABEL 2-3 WORDS CAPS",
  "right_title": "RIGHT LABEL 2-3 WORDS CAPS",
  "left_points": ["point 1 max 10 words", "point 2", "point 3"],
  "right_points": ["point 1 max 10 words", "point 2", "point 3"],
  "caption": "3-4 lines with emoji",
  "hashtags": "..."
}""",

# T2 — Card Grid: 6 numbered tips or facts
BASE + """

Frame as numbered tips, features, or facts people can act on immediately.

JSON format:
{
  "hook_title": "PUNCHY CAPS TITLE max 6 words",
  "subtitle": "one line context max 10 words",
  "category": "AI Models | Humanoid Robots | AI Research | AI Business | AI Tools",
  "points": ["tip 1 max 10 words", "tip 2", "tip 3", "tip 4", "tip 5", "tip 6"],
  "caption": "3-4 lines with emoji",
  "hashtags": "..."
}""",

# T3 — Three Sections: logical grouping into 3 chapters
BASE + """

Group the content into 3 logical sections (e.g. What / How / Why, or Setup / Use / Master, or Problem / Solution / Impact).
Choose section titles that tell a story together. Each section gets exactly 2 points.

JSON format:
{
  "hook_title": "PUNCHY CAPS TITLE max 6 words",
  "subtitle": "one line context max 10 words",
  "sections": [
    {"title": "SECTION ONE 2-3 WORDS CAPS", "points": ["point 1 max 10 words", "point 2"]},
    {"title": "SECTION TWO 2-3 WORDS CAPS", "points": ["point 1 max 10 words", "point 2"]},
    {"title": "SECTION THREE 2-3 WORDS CAPS", "points": ["point 1 max 10 words", "point 2"]}
  ],
  "caption": "3-4 lines with emoji",
  "hashtags": "..."
}""",

# T4 — Light Numbered: 6 clean numbered insights
BASE + """

Frame as numbered insights or steps — clear, sequential, easy to scan.

JSON format:
{
  "hook_title": "PUNCHY CAPS TITLE max 6 words",
  "subtitle": "one line context max 10 words",
  "category": "AI Models | Humanoid Robots | AI Research | AI Business | AI Tools",
  "points": ["insight 1 max 10 words", "insight 2", "insight 3", "insight 4", "insight 5", "insight 6"],
  "caption": "3-4 lines with emoji",
  "hashtags": "..."
}""",
]

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

Transform a news headline into a dense, valuable Instagram infographic.
Every point must be specific and insightful — not generic. Teach something real.

Output ONLY valid JSON, no markdown fences:
{
  "hook_title": "PUNCHY TITLE IN CAPS, max 6 words",
  "subtitle": "One line context, max 10 words",
  "category": "one of: AI Models | Humanoid Robots | AI Research | AI Business | AI Tools",
  "points": ["point 1 max 10 words", "point 2", "point 3", "point 4", "point 5", "point 6"],
  "caption": "3-4 line Instagram caption with emoji, end with: Comment BRIEF → I'll DM you this week's full AI roundup 📩",
  "hashtags": "#AI #ArtificialIntelligence #AINews #NeuralBrief #MachineLearning #AITools #FutureOfAI #TechNews #Robotics #Innovation"
}"""


# ─── TEMPLATE STATE ──────────────────────────────────────────────────────────

def get_and_advance_template():
    """Read current template index from GitHub state.json, then advance it."""
    if not GITHUB_TOKEN:
        return random.randint(0, NUM_TEMPLATES - 1)
    try:
        g     = Github(GITHUB_TOKEN)
        repo  = g.get_repo(GITHUB_REPO)
        file  = repo.get_contents("state.json")
        state = json.loads(file.decoded_content)
        idx   = int(state.get("template_index", 0)) % NUM_TEMPLATES
        next_ = (idx + 1) % NUM_TEMPLATES
        repo.update_file("state.json", f"cycle template → {next_}",
                         json.dumps({"template_index": next_}), file.sha)
        print(f"  Template #{idx} ({TEMPLATE_NAMES[idx]})")
        return idx
    except Exception as e:
        print(f"  State error ({e}), using random")
        return random.randint(0, NUM_TEMPLATES - 1)


# ─── FETCH ───────────────────────────────────────────────────────────────────

def fetch_articles():
    articles = []
    cutoff   = datetime.now(timezone.utc) - timedelta(hours=48)
    for url in SOURCES:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "NeuralBriefBot/1.0"})
            for entry in feed.entries[:6]:
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))[:400]
                pub     = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub and datetime.fromtimestamp(mktime(pub), tz=timezone.utc) < cutoff:
                    continue
                if title and len(title) > 20:
                    articles.append({"title": title, "summary": summary})
        except Exception as e:
            print(f"  Feed error: {e}")
    seen, unique = [], []
    for a in articles:
        key = a["title"][:40].lower()
        if not any(key in s or s in key for s in seen):
            seen.append(key)
            unique.append(a)
    random.shuffle(unique)
    return unique[:20]


# ─── GENERATE ────────────────────────────────────────────────────────────────

def generate_content(article, client, template_idx):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=900,
        system=SYSTEM_PROMPTS[template_idx % NUM_TEMPLATES],
        messages=[{"role": "user", "content":
                   f"Article: {article['title']}\nContext: {article['summary'][:300]}"}],
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
    B = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
         "C:/Windows/Fonts/arialbd.ttf"]
    R = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "C:/Windows/Fonts/arial.ttf"]
    bold = next((p for p in B if os.path.exists(p)), None)
    reg  = next((p for p in R if os.path.exists(p)), None)
    return bold, reg

def F(path, size):
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

def circle_badge(draw, cx, cy, n, fnt, bg, fg, size=40):
    r = size // 2
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=bg)
    t = str(n)
    bb = draw.textbbox((0,0), t, font=fnt)
    draw.text((cx-(bb[2]-bb[0])//2-bb[0], cy-(bb[3]-bb[1])//2-bb[1]), t, font=fnt, fill=fg)

def wrap_line(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textbbox((0,0), test, font=fnt)[2] > max_w and cur:
            lines.append(cur); cur = w
        else:
            cur = test
    if cur: lines.append(cur)
    return lines

def title_y(draw, text, y, bp, color=WHITE, max_w=None, lpad=None):
    max_w = max_w or W - PAD*2
    lpad  = lpad  or PAD
    sz    = 62 if len(text) < 26 else (50 if len(text) < 40 else 40)
    fnt   = F(bp, sz)
    for ln in wrap_line(draw, text, fnt, max_w)[:3]:
        draw.text((lpad, y), ln, font=fnt, fill=color)
        bb = draw.textbbox((0,0), ln, font=fnt)
        y += bb[3]-bb[1]+6
    return y

def header_bar(draw, bp, rp, accent=None):
    c = accent or ACCENT
    draw.rectangle([0, 0, W, 86], fill=c)
    draw.text((PAD, 22), "◆  AI NEURAL BRIEF", font=F(bp, 36), fill=WHITE)
    ds = datetime.now().strftime("%b %d, %Y")
    bb = draw.textbbox((0,0), ds, font=F(rp, 24))
    draw.text((W-PAD-(bb[2]-bb[0]), 28), ds, font=F(rp, 24), fill=WHITE)

def footer(draw, bp, rp, bg=None, handle_color=None, site_color=None):
    draw.rectangle([0, H-76, W, H], fill=bg or CARD)
    draw.text((PAD, H-50), "@aineuralbrief", font=F(bp, 26), fill=handle_color or ACCENT)
    wm = "aineuralbrief.com"
    bb = draw.textbbox((0,0), wm, font=F(rp, 24))
    draw.text((W-PAD-(bb[2]-bb[0]), H-50), wm, font=F(rp, 24), fill=site_color or GREY)

def cat_badge(draw, cat, y, rp):
    cb  = draw.textbbox((0,0), cat, font=F(rp, 22))
    cw  = cb[2]-cb[0]+28
    rr(draw, (PAD, y, PAD+cw, y+34), 8, CARD2)
    draw.text((PAD+14, y+6), cat, font=F(rp, 22), fill=ACCENT)
    return y + 52

def finalize(img):
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf


# ─── TEMPLATE 0: DARK BULLETS ────────────────────────────────────────────────
# Clean dark design, blue accent, diamond bullets

def t0_dark_bullets(content):
    bold, reg = get_fonts()
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    header_bar(draw, bold, reg, ACCENT)
    y = 104
    y = cat_badge(draw, content.get("category","AI News"), y, reg)
    y = title_y(draw, content.get("hook_title","AI UPDATE").upper(), y, bold)
    sub = content.get("subtitle","")
    if sub:
        draw.text((PAD, y+2), sub, font=F(reg, 28), fill=GREY)
        bb = draw.textbbox((0,0), sub, font=F(reg, 28))
        y += bb[3]-bb[1]+16
    draw.rectangle([PAD, y+6, PAD+100, y+10], fill=ACCENT)
    y += 26

    points = content.get("points", [])[:6]
    row_h  = min(74, max(50, (H-86-y-10) // max(len(points),1)))
    for pt in points:
        if y > H-100: break
        bx, by = PAD, y+10
        draw.polygon([(bx+10,by),(bx+20,by+10),(bx+10,by+20),(bx,by+10)], fill=ACCENT)
        draw.text((PAD+34, y+2), pt, font=F(reg, 27), fill=WHITE)
        y += row_h

    footer(draw, bold, reg)
    return finalize(img)


# ─── TEMPLATE 1: COMPARISON TWO-COLUMN ───────────────────────────────────────
# Two columns side by side — "Before vs After" or "Old vs New"

def t1_comparison(content):
    bold, reg = get_fonts()
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    header_bar(draw, bold, reg, DARK)
    y = 100
    y = title_y(draw, content.get("hook_title","AI UPDATE").upper(), y, bold)
    sub = content.get("subtitle","")
    if sub:
        draw.text((PAD, y+2), sub, font=F(reg, 26), fill=GREY)
        bb = draw.textbbox((0,0), sub, font=F(reg, 26))
        y += bb[3]-bb[1]+10
    y += 14

    # Two column layout
    GAP   = 20
    COL_W = (W - PAD*2 - GAP) // 2
    LX    = PAD
    RX    = PAD + COL_W + GAP
    BODY_H = H - 76 - y

    # Column backgrounds
    rr(draw, (LX, y, LX+COL_W, y+BODY_H), 14, CARD2)
    rr(draw, (RX, y, RX+COL_W, y+BODY_H), 14, CARD2)

    # Column header bars
    L_LABEL = content.get("left_title",  "BEFORE")
    R_LABEL = content.get("right_title", "AFTER")
    rr(draw, (LX, y, LX+COL_W, y+52), 14, ACCENT)
    draw.rectangle([LX, y+26, LX+COL_W, y+52], fill=ACCENT)
    rr(draw, (RX, y, RX+COL_W, y+52), 14, ORANGE)
    draw.rectangle([RX, y+26, RX+COL_W, y+52], fill=ORANGE)

    f_lbl = F(bold, 24)
    ll_bb = draw.textbbox((0,0), L_LABEL, font=f_lbl)
    rl_bb = draw.textbbox((0,0), R_LABEL, font=f_lbl)
    draw.text((LX+(COL_W-(ll_bb[2]-ll_bb[0]))//2, y+14), L_LABEL, font=f_lbl, fill=WHITE)
    draw.text((RX+(COL_W-(rl_bb[2]-rl_bb[0]))//2, y+14), R_LABEL, font=f_lbl, fill=WHITE)

    points  = content.get("points", [])[:6]
    left_p  = content.get("left_points",  points[:3])
    right_p = content.get("right_points", points[3:6])
    avail   = BODY_H - 52 - 16
    pt_h    = min(80, avail // max(len(left_p),1))
    f_pt    = F(reg, 25)

    for side_pts, sx in [(left_p, LX), (right_p, RX)]:
        py = y + 64
        for pt in side_pts:
            lines = wrap_line(draw, pt, f_pt, COL_W - 30)
            draw.ellipse([sx+14, py+6, sx+24, py+16], fill=ACCENT if sx==LX else ORANGE)
            ty = py
            for ln in lines[:2]:
                draw.text((sx+32, ty), ln, font=f_pt, fill=WHITE)
                bb = draw.textbbox((0,0), ln, font=f_pt)
                ty += bb[3]-bb[1]+3
            py += pt_h

    footer(draw, bold, reg)
    return finalize(img)


# ─── TEMPLATE 2: NUMBERED CARD GRID ─────────────────────────────────────────
# 2×3 numbered cards with icons — like rubenhassid checklist posts

def t2_card_grid(content):
    bold, reg = get_fonts()
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    header_bar(draw, bold, reg, ACCENT)
    y = 98
    y = title_y(draw, content.get("hook_title","AI UPDATE").upper(), y, bold, max_w=W-PAD*2, lpad=PAD)
    sub = content.get("subtitle","")
    if sub:
        draw.text((PAD, y+2), sub, font=F(reg, 26), fill=GREY)
        bb = draw.textbbox((0,0), sub, font=F(reg, 26))
        y += bb[3]-bb[1]+8
    y += 12

    points = content.get("points", [])[:6]
    GAP   = 14
    COL_W = (W - PAD*2 - GAP) // 2
    avail = H - 86 - y - 10
    ROW_H = (avail - GAP*2) // 3

    CARD_COLORS = [ACCENT, ORANGE, GREEN, PURPLE, ACCENT, ORANGE]
    f_num = F(bold, 24)
    f_txt = F(reg, 24)

    for i, pt in enumerate(points):
        col = i % 2
        row = i // 2
        x1  = PAD + col*(COL_W+GAP)
        y1  = y   + row*(ROW_H+GAP)
        x2, y2 = x1+COL_W, y1+ROW_H
        c   = CARD_COLORS[i]

        rr(draw, (x1, y1, x2, y2), 12, CARD2)
        # Left accent bar
        rr(draw, (x1, y1, x1+8, y2), 6, c)
        # Number badge
        circle_badge(draw, x1+30, y1+ROW_H//2, i+1, f_num, c, WHITE, size=36)
        # Text
        tx   = x1 + 56
        tw   = x2 - tx - 10
        lines = wrap_line(draw, pt, f_txt, tw)
        th   = sum(draw.textbbox((0,0),ln,font=f_txt)[3]-draw.textbbox((0,0),ln,font=f_txt)[1]+4
                   for ln in lines[:2])
        ty   = y1 + (ROW_H - th)//2
        for ln in lines[:2]:
            draw.text((tx, ty), ln, font=f_txt, fill=WHITE)
            bb = draw.textbbox((0,0), ln, font=f_txt)
            ty += bb[3]-bb[1]+4

    footer(draw, bold, reg)
    return finalize(img)


# ─── TEMPLATE 3: THREE SECTIONS ──────────────────────────────────────────────
# 3 grouped sections with colored headers — like guides/checklist rubenhassid posts

def t3_three_sections(content):
    bold, reg = get_fonts()
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    header_bar(draw, bold, reg, ACCENT)
    y = 98
    y = title_y(draw, content.get("hook_title","AI UPDATE").upper(), y, bold)
    sub = content.get("subtitle","")
    if sub:
        draw.text((PAD, y+2), sub, font=F(reg, 26), fill=GREY)
        bb = draw.textbbox((0,0), sub, font=F(reg, 26))
        y += bb[3]-bb[1]+8
    y += 12

    sec_colors  = [ACCENT, ORANGE, GREEN]
    raw_sections = content.get("sections", [])
    # fallback: split points into 3 groups if sections key missing
    if not raw_sections:
        pts = content.get("points", [])[:6]
        raw_sections = [
            {"title": "UNDERSTAND IT", "points": pts[0:2]},
            {"title": "USE IT",        "points": pts[2:4]},
            {"title": "MASTER IT",     "points": pts[4:6]},
        ]
    sec_titles = [s.get("title","SECTION") for s in raw_sections[:3]]
    sections   = [s.get("points", [])[:2] for s in raw_sections[:3]]

    GAP   = 12
    avail = H - 86 - y - 10
    SEC_H = (avail - GAP*2) // 3
    f_sh  = F(bold, 24)
    f_pt  = F(reg, 26)

    for i, (title, pts, color) in enumerate(zip(sec_titles, sections, sec_colors)):
        sy = y + i*(SEC_H+GAP)
        rr(draw, (PAD, sy, W-PAD, sy+SEC_H), 12, CARD2)
        # Section header bar
        rr(draw, (PAD, sy, W-PAD, sy+48), 12, color)
        draw.rectangle([PAD, sy+24, W-PAD, sy+48], fill=color)
        # Section title with small icon
        draw.polygon([(PAD+18,sy+18),(PAD+28,sy+24),(PAD+18,sy+30),(PAD+8,sy+24)], fill=WHITE)
        draw.text((PAD+36, sy+13), title, font=f_sh, fill=WHITE)
        # Points
        py = sy + 58
        for pt in pts[:2]:
            if py > sy + SEC_H - 10: break
            draw.ellipse([PAD+14, py+7, PAD+24, py+17], fill=color)
            draw.text((PAD+34, py), pt, font=f_pt, fill=WHITE)
            bb = draw.textbbox((0,0), pt, font=f_pt)
            py += bb[3]-bb[1]+10

    footer(draw, bold, reg)
    return finalize(img)


# ─── TEMPLATE 4: LIGHT CLEAN NUMBERED ────────────────────────────────────────
# Cream background, bold numbers, clean typography — like rubenhassid's text-heavy posts

def t4_light_numbered(content):
    bold, reg = get_fonts()
    img  = Image.new("RGB", (W, H), CREAM)
    draw = ImageDraw.Draw(img)

    # Top bar
    draw.rectangle([0, 0, W, 8], fill=ACCENT)
    # Brand
    y = 28
    draw.text((PAD, y), "AI NEURAL BRIEF", font=F(bold, 30), fill=ACCENT)
    ds = datetime.now().strftime("%b %d, %Y")
    bb = draw.textbbox((0,0), ds, font=F(reg, 24))
    draw.text((W-PAD-(bb[2]-bb[0]), y+4), ds, font=F(reg, 24), fill=(130,125,115))
    y += 52

    # Category
    cat = content.get("category", "AI News")
    cb  = draw.textbbox((0,0), cat, font=F(reg, 22))
    rr(draw, (PAD, y, PAD+cb[2]-cb[0]+28, y+34), 8, ACCENT)
    draw.text((PAD+14, y+6), cat, font=F(reg, 22), fill=WHITE)
    y += 52

    # Title
    y = title_y(draw, content.get("hook_title","AI UPDATE").upper(), y, bold,
                color=DARK, max_w=W-PAD*2, lpad=PAD)
    sub = content.get("subtitle","")
    if sub:
        draw.text((PAD, y+2), sub, font=F(reg, 28), fill=(100,100,120))
        bb = draw.textbbox((0,0), sub, font=F(reg, 28))
        y += bb[3]-bb[1]+10
    draw.rectangle([PAD, y+6, W-PAD, y+3], fill=ACCENT)
    y += 22

    points = content.get("points", [])[:6]
    row_h  = min(88, max(54, (H-72-y) // max(len(points),1)))
    f_num  = F(bold, 36)
    f_pt   = F(reg, 27)

    for i, pt in enumerate(points, 1):
        if y > H-90: break
        # Large number
        num_s = str(i)
        nb    = draw.textbbox((0,0), num_s, font=f_num)
        draw.text((PAD, y), num_s, font=f_num, fill=ACCENT)
        nw    = nb[2]-nb[0]+14
        # Separator line next to number
        draw.rectangle([PAD+nw, y+16, PAD+nw+4, y+36], fill=ORANGE)
        # Point text
        lines = wrap_line(draw, pt, f_pt, W-PAD-nw-20-PAD)
        ty    = y + max(0, (40-len(lines)*32)//2)
        for ln in lines[:2]:
            draw.text((PAD+nw+16, ty), ln, font=f_pt, fill=DARK)
            bb = draw.textbbox((0,0), ln, font=f_pt)
            ty += bb[3]-bb[1]+4
        y += row_h

    # Light footer
    draw.rectangle([0, H-72, W, H], fill=(225, 220, 212))
    draw.text((PAD, H-48), "@aineuralbrief", font=F(bold, 26), fill=ACCENT)
    wm = "aineuralbrief.com"
    bb = draw.textbbox((0,0), wm, font=F(reg, 24))
    draw.text((W-PAD-(bb[2]-bb[0]), H-48), wm, font=F(reg, 24), fill=(110,105,95))
    return finalize(img)


# ─── TEMPLATE REGISTRY ───────────────────────────────────────────────────────

TEMPLATE_NAMES = [
    "Dark Bullets",
    "Comparison Two-Col",
    "Card Grid",
    "Three Sections",
    "Light Numbered",
]
TEMPLATES = [t0_dark_bullets, t1_comparison, t2_card_grid, t3_three_sections, t4_light_numbered]

def render_image(content, template_idx):
    return TEMPLATES[template_idx % NUM_TEMPLATES](content)


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
    print(f"[{datetime.now().isoformat()}] AI Neural Brief — {POSTS_PER_RUN} post(s)")
    client       = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    template_idx = get_and_advance_template()
    articles     = fetch_articles()
    print(f"  Fetched {len(articles)} articles")
    if not articles:
        print("  No articles found, exiting")
        return
    step     = max(1, len(articles) // POSTS_PER_RUN)
    selected = articles[::step][:POSTS_PER_RUN]
    for i, article in enumerate(selected, 1):
        print(f"  [{i}/{len(selected)}] {article['title'][:70]}")
        try:
            # Each post in a run uses consecutive templates
            idx       = (template_idx + i - 1) % NUM_TEMPLATES
            content   = generate_content(article, client, idx)
            image_buf = render_image(content, idx)
            caption   = content.get("caption","") + "\n\n" + content.get("hashtags","")
            send_telegram(image_buf, caption)
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            import traceback; traceback.print_exc()
    print("  Done.")


if __name__ == "__main__":
    main()
