import feedparser

RSS_URL = "https://www.wired.com/feed/tag/ai/latest/rss"

feed = feedparser.parse(RSS_URL)

print("Total news:", len(feed.entries))
print()

for entry in feed.entries:
    print("TITLE:", entry.get("title", "No title"))
    print("LINK:", entry.get("link", "No link"))
    print("DATE:", entry.get("published", "No date"))
    print("SUMMARY:", entry.get("summary", "No summary")[:300])
    print("=" * 70)