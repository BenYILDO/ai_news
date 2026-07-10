import os, requests

bot = os.environ["TELEGRAM_BOT_TOKEN"]
r = requests.get(f"https://api.telegram.org/bot{bot}/getUpdates", timeout=30)
r.raise_for_status()
updates = r.json().get("result", [])
chats = {}
for update in updates:
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    if chat.get("id"):
        chats[chat["id"]] = chat.get("username") or chat.get("first_name") or chat.get("title") or "unknown"
if not chats:
    raise SystemExit("Chat bulunamadi. Telegram'da bota /start yazip workflow'u tekrar calistir.")
for chat_id, name in chats.items():
    print(f"TELEGRAM_CHAT_ID={chat_id} ({name})")
