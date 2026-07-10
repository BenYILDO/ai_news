import os, requests
from common import sb_get, sb_post

BOT=os.environ["TELEGRAM_BOT_TOKEN"]

def offset():
    rows=sb_get("bot_state", {"key":"eq.telegram_offset","select":"value","limit":"1"})
    return int(rows[0]["value"]) if rows else 0

def save_offset(value):
    sb_post("bot_state?on_conflict=key", {"key":"telegram_offset","value":str(value)}, "resolution=merge-duplicates,return=minimal")

if __name__ == "__main__":
    r=requests.get(f"https://api.telegram.org/bot{BOT}/getUpdates",params={"offset":offset(),"timeout":0},timeout=30); r.raise_for_status()
    updates=r.json().get("result",[])
    for update in updates:
        query=update.get("callback_query")
        if query and ":" in query.get("data",""):
            choice, article_id=query["data"].split(":",1)
            if choice in {"like","skip","linkedin"}:
                sb_post("feedback?on_conflict=article_id,choice", {"article_id":article_id,"choice":choice}, "resolution=ignore-duplicates,return=minimal")
                requests.post(f"https://api.telegram.org/bot{BOT}/answerCallbackQuery",json={"callback_query_id":query["id"],"text":"Tercihin kaydedildi ✅"},timeout=30)
        save_offset(update["update_id"]+1)

