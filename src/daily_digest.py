import hashlib, html, json, os, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
import feedparser, requests
from dateutil import parser as dtparser
from common import sb_get, sb_post, sb_patch

BOT = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT = os.environ["TELEGRAM_CHAT_ID"]

def clean(value, limit=650):
    value = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", value).strip()[:limit]

def published(entry):
    raw = entry.get("published") or entry.get("updated")
    try:
        return dtparser.parse(raw).astimezone(timezone.utc) if raw else datetime.now(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

def preferences():
    rows = sb_get("feedback", {"select":"choice,articles(source,category)", "order":"created_at.desc", "limit":"300"})
    weights = {}
    points = {"like":2, "linkedin":4, "skip":-2}
    for row in rows:
        article = row.get("articles") or {}
        for key in (article.get("source"), article.get("category")):
            if key: weights[key] = weights.get(key, 0) + points.get(row["choice"], 0)
    return weights

def collect():
    feeds = json.loads(Path("config/feeds.json").read_text())
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    weights, found = preferences(), {}
    for feed in feeds:
        parsed = feedparser.parse(feed["url"])
        for e in parsed.entries[:25]:
            url, title, pub = e.get("link"), clean(e.get("title"), 240), published(e)
            if not url or not title or pub < cutoff: continue
            key = hashlib.sha256((title.lower()+url).encode()).hexdigest()
            age = max(0, (datetime.now(timezone.utc)-pub).total_seconds()/3600)
            score = 100 - min(age, 100) + weights.get(feed["name"],0) + weights.get(feed["category"],0)
            found[key] = {"url":url,"title":title,"summary":clean(e.get("summary") or e.get("description")),"source":feed["name"],"category":feed["category"],"published_at":pub.isoformat(),"score":round(score,2)}
    return sorted(found.values(), key=lambda x:x["score"], reverse=True)

def save(items):
    saved=[]
    for item in items[:40]:
        try:
            saved += sb_post("articles?on_conflict=url", item, "resolution=merge-duplicates,return=representation")
        except requests.HTTPError as exc:
            print(exc.response.text)
    return saved

def idea(article):
    angles={"lojistik":"Bu gelişme lojistik operasyonlarında neyi değiştirir?","otomasyon":"Bunu gerçek bir iş sürecine nasıl uygularız?","yazilim":"Geliştiriciler ve işletmeler için pratik etkisi ne?","yapay-zeka":"Abartıdan uzak, iş dünyası için gerçek karşılığı ne?"}
    return angles.get(article["category"], "Bu gelişmenin iş dünyasına somut etkisi ne?")

def send(article, number):
    text=f"<b>{number}. {html.escape(article['title'])}</b>\n\n{html.escape(article.get('summary') or 'Özet bulunamadı.')}\n\n💡 <b>LinkedIn açısı:</b> {html.escape(idea(article))}\n\n<a href=\"{html.escape(article['url'])}\">Kaynağı aç</a> · {html.escape(article['source'])}"
    aid=article["id"]
    keyboard={"inline_keyboard":[[{"text":"🇹🇷 Türkçe oku","callback_data":f"translate:{aid}"},{"text":"📝 Özetle","callback_data":f"summarize:{aid}"}],[{"text":"👍 Beğendim","callback_data":f"like:{aid}"},{"text":"👎 Geç","callback_data":f"skip:{aid}"}],[{"text":"✍️ LinkedIn'de kullanacağım","callback_data":f"linkedin:{aid}"}]]}
    r=requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",json={"chat_id":CHAT,"text":text,"parse_mode":"HTML","disable_web_page_preview":True,"reply_markup":keyboard},timeout=30)
    r.raise_for_status(); mid=r.json()["result"]["message_id"]
    sb_patch("articles", {"id":f"eq.{article['id']}"}, {"telegram_message_id":mid})

if __name__ == "__main__":
    save(collect())
    params={"select":"*","order":"score.desc","limit":"10"}
    if os.environ.get("FORCE_SEND","false").lower()!="true":
        params["telegram_message_id"]="is.null"
    top=sb_get("articles", params)
    requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",json={"chat_id":CHAT,"text":"☀️ Günlük AI & LinkedIn radarın hazır. Seçimlerin yarının listesini iyileştirecek."},timeout=30).raise_for_status()
    for i,a in enumerate(top,1): send(a,i)
