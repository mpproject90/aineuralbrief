#!/usr/bin/env python3
"""AI Neural Brief — Daily Instagram content generator"""

import os
import io
import json
import textwrap
import requests
import feedparser
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
WHITE  = (255, 255, 255)
GREY   = (140, 150, 170)
W, H   = 1080, 1080

# ─── RSS SOURCES ─────────────────────────────────────────────────────────────
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
  "points": ["point 1 max 8 words", "point 2", "point 3", "point 4", "point 5", "point 6", "point 7"],
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
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))[:400]

                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub:
                    pub_dt = datetime.fromtimestamp(mktime(pub), tz=timezone.utc)
                    if pub_dt < cutoff:
                        continue

                if title and len(title) > 20:
                    articles.append({
                        "title": title,
                        "summary": summary,
                        "source": feed.feed.get("title", ""),
                    })
        except Exception as e:
            print(f"  Source error: {e}")

    # Deduplicate by title prefix
    seen, unique = [], []
    for a in articles:
        key = a["title"][:40].lower()
        if not any(key in s or s in key for s in seen):
            seen.append(key)
            unique.append(a)

    return unique[:20]


# ─── GENERATE ────────────────────────────────────────────────────────────────

def generate_content(article, client):
    prompt = f"Article: {article['title']}\nContext: {article['summary'][:300]}"

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


# ─── RENDER ──────────────────────────────────────────────────────────────────

def load_font(path, size):
    try:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    return ImageFont.load_default()


def get_font_paths():
    bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    reg_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    bold = next((p for p in bold_candidates if os.path.exists(p)), None)
    reg  = next((p for p in reg_candidates if os.path.exists(p)), None)
    return bold, reg


def draw_rounded_rect(draw, xy, radius, fill):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
    draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
    draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
    draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)


def render_image(content):
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    bold, reg = get_font_paths()
    f_brand  = load_font(bold, 38)
    f_date   = load_font(reg,  26)
    f_cat    = load_font(reg,  24)
    f_title  = load_font(bold, 64)
    f_sub    = load_font(reg,  30)
    f_point  = load_font(reg,  27)
    f_footer = load_font(bold, 26)

    PAD = 60

    # ── Header bar ────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, 88], fill=ACCENT)
    draw.text((PAD, 24), "◆  AI NEURAL BRIEF", font=f_brand, fill=WHITE)
    date_str = datetime.now().strftime("%b %d, %Y")
    d_bbox = draw.textbbox((0, 0), date_str, font=f_date)
    draw.text((W - PAD - (d_bbox[2] - d_bbox[0]), 30), date_str, font=f_date, fill=WHITE)

    y = 112

    # ── Category badge ────────────────────────────────────────────────────────
    cat = content.get("category", "🤖 AI Models")
    c_bbox = draw.textbbox((0, 0), cat, font=f_cat)
    cat_w = c_bbox[2] - c_bbox[0] + 32
    draw_rounded_rect(draw, (PAD, y, PAD + cat_w, y + 36), 8, CARD)
    draw.text((PAD + 16, y + 6), cat, font=f_cat, fill=ACCENT)
    y += 56

    # ── Title ─────────────────────────────────────────────────────────────────
    title = content.get("hook_title", "AI UPDATE").upper()
    title_size = 64 if len(title) < 28 else (52 if len(title) < 42 else 42)
    f_title = load_font(bold, title_size)
    max_w = W - PAD * 2

    words, lines, current = title.split(), [], ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=f_title)
        if bbox[2] - bbox[0] > max_w and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    for line in lines[:3]:
        draw.text((PAD, y), line, font=f_title, fill=WHITE)
        bbox = draw.textbbox((0, 0), line, font=f_title)
        y += bbox[3] - bbox[1] + 6

    # ── Subtitle ──────────────────────────────────────────────────────────────
    subtitle = content.get("subtitle", "")
    if subtitle:
        y += 4
        draw.text((PAD, y), subtitle, font=f_sub, fill=GREY)
        bbox = draw.textbbox((0, 0), subtitle, font=f_sub)
        y += bbox[3] - bbox[1] + 16

    # ── Divider ───────────────────────────────────────────────────────────────
    draw.rectangle([PAD, y, PAD + 90, y + 4], fill=ACCENT)
    y += 26

    # ── Points ────────────────────────────────────────────────────────────────
    points = content.get("points", [])[:7]
    available_h = H - 90 - y  # space above footer
    row_h = max(44, available_h // max(len(points), 1))
    row_h = min(row_h, 68)

    for point in points:
        if y > H - 110:
            break

        # Diamond bullet
        bx, by = PAD, y + 10
        draw.polygon(
            [(bx + 10, by), (bx + 20, by + 10), (bx + 10, by + 20), (bx, by + 10)],
            fill=ACCENT,
        )

        # Text (single line — prompt enforces ≤8 words)
        draw.text((PAD + 34, y + 2), point, font=f_point, fill=WHITE)
        y += row_h

    # ── Footer with watermark ─────────────────────────────────────────────────
    draw.rectangle([0, H - 78, W, H], fill=CARD)
    draw.text((PAD, H - 52), "@aineuralbrief", font=f_footer, fill=ACCENT)
    wm = "aineuralbrief.com"
    wm_bbox = draw.textbbox((0, 0), wm, font=f_footer)
    draw.text((W - PAD - (wm_bbox[2] - wm_bbox[0]), H - 52), wm, font=f_footer, fill=GREY)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf


# ─── TELEGRAM ────────────────────────────────────────────────────────────────

def send_telegram(image_buf, caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
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
