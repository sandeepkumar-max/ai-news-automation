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
# Flask
# =========================

@app.route("/")
def home():
    return "AI News Automation Bot is running! 🤖"


@app.route("/health")
def health():
    return "OK"


# =========================
# Telegram
# =========================

def telegram_request(method, data=None):
    try:
        response = requests.post(
            f"{TELEGRAM_URL}/{method}",
            json=data or {},
            timeout=30
        )

        print("Telegram", method, response.status_code)
        return response.json()

    except Exception as e:
        print("Telegram Error:", e)
        return None


def send_telegram(chat_id, text, buttons=None):

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if buttons:
        data["reply_markup"] = {
            "inline_keyboard": buttons
        }

    return telegram_request("sendMessage", data)


# =========================
# Main Menu
# =========================

def main_menu(chat_id):

    buttons = [
        [
            {"text": "📰 Latest News", "callback_data": "latest"},
            {"text": "🤖 Ask AI", "callback_data": "ask"}
        ],
        [
            {"text": "🔄 Check News", "callback_data": "check"},
            {"text": "ℹ️ Help", "callback_data": "help"}
        ]
    ]

    send_telegram(
        chat_id,
        "🤖 AI News Bot\n\n"
        "Welcome! नीचे से कोई option चुनें 👇",
        buttons
    )


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

            result = response.json()

            return result["choices"][0]["message"]["content"]

        print("Groq Error:", response.status_code)
        print(response.text)

        return "AI से response नहीं मिला। थोड़ी देर बाद फिर कोशिश करें."

    except Exception as e:

        print("Groq Exception:", e)

        return "AI service में अभी problem है."


# =========================
# Create News Article
# =========================

def create_article(title, summary):

    prompt = f"""
You are an AI technology news writer.

Write a natural Hindi news article based ONLY on the information provided.

News Title:
{title}

News Summary:
{summary}

Rules:

- Write in simple natural Hindi.
- Around 500-700 words.
- Start with an interesting introduction.
- Explain the news clearly.
- Add useful context only when supported.
- Do not make up facts.
- Keep important technical English terms.
- Use short paragraphs.
- Add a natural conclusion.
- Do not mention that AI wrote the article.

Now write the article.
"""

    return ask_groq(prompt)


# =========================
# Get Latest News
# =========================

def get_latest_news():

    try:

        feed = feedparser.parse(RSS_URL)

        if not feed.entries:
            return None

        entry = feed.entries[0]

        return {
            "title": entry.get("title", "No title"),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", "")[:1500]
        }

    except Exception as e:

        print("RSS Error:", e)
        return None


# =========================
# Send News
# =========================

def send_news(chat_id, news):

    global pending_article

    if not news:
        send_telegram(
            chat_id,
            "❌ अभी news नहीं मिल पाई।"
        )
        return

    send_telegram(
        chat_id,
        "⏳ News मिल गई!\n\nAI article तैयार कर रहा हूँ..."
    )

    article = create_article(
        news["title"],
        news["summary"]
    )

    # Save article for approval/edit
    pending_article = {
        "title": news["title"],
        "link": news["link"],
        "article": article
    }

    message = (
        "📰 AI NEWS - REVIEW\n\n"
        f"{article}\n\n"
        f"🔗 Source: {news['link']}"
    )

    if len(message) > 4000:
        message = message[:3950] + "\n\n🔗 Source: " + news["link"]

    buttons = [
        [
            {"text": "🟢 APPROVE", "callback_data": "approve"},
            {"text": "🔴 REJECT", "callback_data": "reject"}
        ],
        [
            {"text": "✏️ EDIT / IMPROVE", "callback_data": "edit"}
        ],
        [
            {
                "text": "🔗 Read Original",
                "url": news["link"]
            }
        ]
    ]

    send_telegram(
        chat_id,
        message,
        buttons
    )


# =========================
# Automatic News Worker
# =========================

last_news_link = None

# =========================
# Pending Article
# =========================

pending_article = None
awaiting_edit = False


def news_worker():

    global last_news_link

    print("News worker started.")

    while True:

        try:

            news = get_latest_news()

            if news:

                link = news["link"]

                if link and link != last_news_link:

                    print("New article found:", news["title"])

                    send_news(CHAT_ID, news)

                    last_news_link = link

                else:

                    print("No new news.")

        except Exception as e:

            print("News Worker Error:", e)

        # Check every 30 minutes
        time.sleep(1800)


# =========================
# Telegram Worker
# =========================

def telegram_worker():

    print("Telegram worker started.")

    offset = 0

    while True:

        try:

            response = requests.get(
                f"{TELEGRAM_URL}/getUpdates",
                params={
                    "offset": offset,
                    "timeout": 30
                },
                timeout=40
            )

            data = response.json()

            if not data.get("ok"):

                print("Telegram getUpdates error:", data)

                time.sleep(5)
                continue

            for update in data.get("result", []):

                offset = update["update_id"] + 1

                # =====================
                # Button Click
                # =====================

                callback = update.get("callback_query")

                if callback:

                    callback_id = callback["id"]
                    chat_id = callback["message"]["chat"]["id"]
                    action = callback.get("data")

                    # Remove loading animation
                    requests.post(
                        f"{TELEGRAM_URL}/answerCallbackQuery",
                        json={
                            "callback_query_id": callback_id
                        },
                        timeout=20
                    )
                                         if action == "approve":

                        global pending_article

                        if pending_article:

                            send_telegram(
                                chat_id,
                                "✅ Article APPROVED!\n\n"
                                "यह article publish करने के लिए ready है."
                            )

                            pending_article = None

                        else:

                            send_telegram(
                                chat_id,
                                "⚠️ कोई pending article नहीं है."
                            )


                    elif action == "reject":

                        pending_article = None

                        send_telegram(
                            chat_id,
                            "❌ Article REJECTED.\n\n"
                            "यह article आगे इस्तेमाल नहीं किया जाएगा."
                        )


                    elif action == "edit":

                        global awaiting_edit

                        if pending_article:

                            awaiting_edit = True

                            send_telegram(
                                chat_id,
                                "✏️ बताइए article में क्या बदलना है.\n\n"
                                "Example:\n"
                                "Introduction ज्यादा powerful करो.\n\n"
                                "या:\n"
                                "Article को ज्यादा practical बनाओ."
                            )

                        else:

                            send_telegram(
                                chat_id,
                                "⚠️ Edit करने के लिए कोई pending article नहीं है."
                            )


                    elif action == "latest":
                    if action == "latest":
                        

                        news = get_latest_news()
                        send_news(chat_id, news)

                    elif action == "check":

                        send_telegram(
                            chat_id,
                            "🔍 Latest news check कर रहा हूँ..."
                        )

                        news = get_latest_news()

                        if news:
                            send_news(chat_id, news)
                        else:
                            send_telegram(
                                chat_id,
                                "❌ अभी news नहीं मिली."
                            )

                    elif action == "ask":

                        send_telegram(
                            chat_id,
                            "🤖 अपना सवाल लिखकर भेजिए.\n\n"
                            "Example:\n"
                            "AI क्या है?"
                        )

                    elif action == "help":

                        send_telegram(
                            chat_id,
                            "ℹ️ AI News Bot Help\n\n"
                            "📰 Latest News = latest AI news\n"
                            "🔄 Check News = अभी news check करें\n"
                            "🤖 Ask AI = AI से सवाल पूछें\n"
                            "ℹ️ Help = यह menu\n\n"
                            "आप सीधे कोई भी सवाल भी भेज सकते हैं."
                        )

                    continue

                # =====================
                # Normal Message
                # =====================

                message = update.get("message")

                if not message:
                    continue

                text = message.get("text", "")
                chat_id = message["chat"]["id"]

                if not text:
                    continue
                
                print("Message received:", text)
                                # =====================
                # Article Edit Request
                # =====================

                if awaiting_edit and pending_article:

                    old_article = pending_article["article"]

                    edit_prompt = f"""
You are editing an AI technology news article.

Original article:
{old_article}

User's requested changes:
{text}

Rewrite the article according to the user's request.

Rules:
- Keep the facts accurate.
- Do not invent information.
- Keep it natural Hindi.
- Keep useful technical English terms.
- Improve the article instead of simply shortening it.
- Do not mention AI or this editing process.
"""

                    edited_article = ask_groq(edit_prompt)

                    pending_article["article"] = edited_article

                    awaiting_edit = False

                    message = (
                        "✏️ UPDATED ARTICLE - REVIEW\n\n"
                        f"{edited_article}\n\n"
                        f"🔗 Source: {pending_article['link']}"
                    )

                    if len(message) > 4000:
                        message = message[:3950] + (
                            "\n\n🔗 Source: "
                            + pending_article["link"]
                        )

                    buttons = [
                        [
                            {
                                "text": "🟢 APPROVE",
                                "callback_data": "approve"
                            },
                            {
                                "text": "🔴 REJECT",
                                "callback_data": "reject"
                            }
                        ],
                        [
                            {
                                "text": "✏️ EDIT / IMPROVE",
                                "callback_data": "edit"
                            }
                        ]
                    ]

                    send_telegram(
                        chat_id,
                        message,
                        buttons
                    )

                    continue

                # /start
                if text == "/start":

                    main_menu(chat_id)

                # Normal user question
                else:

                    reply = ask_groq(
                        f"""
You are a helpful Telegram AI assistant.

Reply naturally and clearly.

Use simple Hindi/Hinglish when appropriate.

User message:
{text}
"""
                    )

                    send_telegram(
                        chat_id,
                        reply,
                        [
                            [
                                {"text": "📰 Latest News", "callback_data": "latest"},
                                {"text": "🤖 Ask AI", "callback_data": "ask"}
                            ],
                            [
                                {"text": "🔄 Check News", "callback_data": "check"},
                                {"text": "ℹ️ Help", "callback_data": "help"}
                            ]
                        ]
                    )

        except Exception as e:

            print("Telegram Worker Error:", e)

            time.sleep(5)


# =========================
# Start Workers
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

    port = int(
        os.environ.get("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
      )
