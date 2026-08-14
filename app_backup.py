import os
import time
import threading
import requests
import feedparser

from flask import Flask

app = Flask(__name__)

# =========================
# Environment Variables
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

RSS_URL = "https://www.wired.com/feed/tag/ai/latest/rss"

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


# =========================
# Flask Routes
# =========================

@app.route("/")
def home():
    return "AI News Automation Bot is running!"


@app.route("/health")
def health():
    return "OK"


# =========================
# Telegram Message
# =========================

def send_telegram(message):
    try:
        response = requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": message
            },
            timeout=30
        )

        print("Telegram:", response.status_code)

    except Exception as e:
        print("Telegram Error:", e)


# =========================
# Groq AI
# =========================

def ask_groq(prompt):

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.65,
        "max_tokens": 1300
    }

    try:

        response = requests.post(
            GROQ_URL,
            headers=headers,
            json=data,
            timeout=60
        )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]

        return f"AI Error: {response.text}"

    except Exception as e:
        return f"AI Error: {e}"


# =========================
# Create Article
# =========================

def create_article(title, summary):

    prompt = f"""
You are an AI technology news writer.

Write a natural Hindi article based on this news.

News Title:
{title}

News Summary:
{summary}

Rules:

- Write in simple natural Hindi.
- Around 500-700 words.
- Start with an interesting introduction.
- Explain the news clearly.
- Add useful context.
- Do not make up facts.
- Keep technical English terms where necessary.
- Use short paragraphs.
- Add a natural conclusion.
- Do not mention that AI wrote the article.

Now write the article.
"""

    return ask_groq(prompt)


# =========================
# Automatic News
# =========================

last_news_link = None


def news_worker():

    global last_news_link

    print("News worker started.")

    while True:

        try:

            feed = feedparser.parse(RSS_URL)

            if feed.entries:

                entry = feed.entries[0]

                title = entry.get("title", "No title")
                link = entry.get("link", "")
                summary = entry.get("summary", "")[:1000]

                # Don't send same news again
                if link and link != last_news_link:

                    print("New article found:", title)

                    article = create_article(title, summary)

                    message = (
                        "📰 AI NEWS\n\n"
                        f"{article}\n\n"
                        f"🔗 Source: {link}"
                    )

                    send_telegram(message)

                    last_news_link = link

                else:

                    print("No new news.")

        except Exception as e:

            print("News Worker Error:", e)

        # Check every 30 minutes
        time.sleep(1800)


# =========================
# Telegram Reply Worker
# =========================

def telegram_worker():

   print("BOT TOKEN exists:", bool(BOT_TOKEN))
print("CHAT ID exists:", bool(CHAT_ID))
print("GROQ KEY exists:", bool(GROQ_API_KEY))

try:
    webhook = requests.get(
        f"{TELEGRAM_URL}/getWebhookInfo",
        timeout=20
    )
    print("Webhook Info:", webhook.text)

    delete = requests.get(
        f"{TELEGRAM_URL}/deleteWebhook",
        params={"drop_pending_updates": True},
        timeout=20
    )
    print("Delete Webhook:", delete.text)

except Exception as e:
    print("Telegram setup error:", e)


# =========================
# Start Background Workers
# =========================

threading.Thread(
    target=telegram_worker,
    daemon=True
).start()

threading.Thread(
    target=news_worker,
    daemon=True
).start()


# =========================
# Start Flask
# =========================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
            )
