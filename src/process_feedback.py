import os, re, requests
from bs4 import BeautifulSoup
from common import sb_get, sb_post

BOT=os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI=os.environ.get("GEMINI_API_KEY")
MODEL=os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")

def offset():
    rows=sb_get("bot_state", {"key":"eq.telegram_offset","select":"value","limit":"1"})
    return int(rows[0]["value"]) if rows else 0

def save_offset(value):
    sb_post("bot_state?on_conflict=key", {"key":"telegram_offset","value":str(value)}, "resolution=merge-duplicates,return=minimal")

def article(article_id):
    rows=sb_get("articles", {"id":f"eq.{article_id}","select":"id,title,url,summary","limit":"1"})
    return rows[0] if rows else None

def article_text(item):
    try:
        r=requests.get(item["url"],headers={"User-Agent":"Mozilla/5.0 AI-News-Radar/1.0"},timeout=25)
        r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        for tag in soup(["script","style","nav","header","footer","aside","form"]): tag.decompose()
        candidates=soup.select("article p") or soup.select("main p") or soup.select("p")
        text="\n".join(p.get_text(" ",strip=True) for p in candidates)
        text=re.sub(r"\n{3,}","\n\n",text).strip()
        if len(text) >= 500: return text[:30000]
    except Exception as exc:
        print(f"Article fetch failed: {exc}")
    return item.get("summary") or item["title"]

def gemini(prompt):
    if not GEMINI: raise RuntimeError("GEMINI_API_KEY tanimli degil")
    r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",headers={"x-goog-api-key":GEMINI,"Content-Type":"application/json"},json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.2,"maxOutputTokens":6000}},timeout=120)
    r.raise_for_status()
    parts=r.json()["candidates"][0]["content"]["parts"]
    return "\n".join(p.get("text","") for p in parts).strip()

def send_chunks(chat_id, heading, text):
    chunks=[]
    while text:
        cut=min(3800,len(text))
        if cut < len(text):
            pivot=max(text.rfind("\n",0,cut),text.rfind(". ",0,cut))
            if pivot>1800: cut=pivot+1
        chunks.append(text[:cut].strip()); text=text[cut:].strip()
    for i,chunk in enumerate(chunks):
        prefix=f"{heading}\n\n" if i==0 else f"{heading} ({i+1}/{len(chunks)})\n\n"
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",json={"chat_id":chat_id,"text":prefix+chunk,"disable_web_page_preview":True},timeout=30).raise_for_status()

def ai_action(choice, item):
    body=article_text(item)
    if choice=="translate":
        prompt=f"Aşağıdaki haber metnini anlamı ve önemli ayrıntıları koruyarak doğal, akıcı Türkçeye çevir. Reklam, menü ve alakasız site metinlerini çıkar. Yalnızca Türkçe çeviriyi ver.\n\nBaşlık: {item['title']}\nKaynak: {item['url']}\n\n{body}"
        return "🇹🇷 Türkçe haber", gemini(prompt)
    prompt=f"Aşağıdaki haberi Türkçe olarak özetle. Önce 2-3 cümlelik ana özet, ardından en fazla 5 maddede önemli noktalar ve son olarak 'LinkedIn için çıkarım' başlığı altında tek bir uygulanabilir fikir ver. Metinde olmayan bilgi ekleme.\n\nBaşlık: {item['title']}\nKaynak: {item['url']}\n\n{body}"
    return "📝 Türkçe özet", gemini(prompt)

if __name__ == "__main__":
    r=requests.get(f"https://api.telegram.org/bot{BOT}/getUpdates",params={"offset":offset(),"timeout":0},timeout=30); r.raise_for_status()
    updates=r.json().get("result",[])
    for update in updates:
        query=update.get("callback_query")
        try:
            if query and ":" in query.get("data",""):
                choice, article_id=query["data"].split(":",1)
                if choice in {"like","skip","linkedin"}:
                    sb_post("feedback?on_conflict=article_id,choice", {"article_id":article_id,"choice":choice}, "resolution=ignore-duplicates,return=minimal")
                    requests.post(f"https://api.telegram.org/bot{BOT}/answerCallbackQuery",json={"callback_query_id":query["id"],"text":"Tercihin kaydedildi ✅"},timeout=30)
                elif choice in {"translate","summarize"}:
                    requests.post(f"https://api.telegram.org/bot{BOT}/answerCallbackQuery",json={"callback_query_id":query["id"],"text":"Hazırlıyorum…"},timeout=30)
                    item=article(article_id)
                    if not item: raise RuntimeError("Haber bulunamadi")
                    heading, result=ai_action(choice,item)
                    send_chunks(query["message"]["chat"]["id"],heading,result)
        except Exception as exc:
            print(f"Callback failed: {exc}")
            if query:
                requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",json={"chat_id":query["message"]["chat"]["id"],"text":"İşlem şu an tamamlanamadı. Lütfen biraz sonra tekrar dene."},timeout=30)
        finally:
            save_offset(update["update_id"]+1)
