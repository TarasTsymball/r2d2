import sys

bot_token  = sys.argv[1]
chat_id    = sys.argv[2]
pc_name    = sys.argv[3]
server_url = sys.argv[4]

with open("tg.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("PLACEHOLDER_TOKEN",  bot_token)
content = content.replace("PLACEHOLDER_CHATID", chat_id)
content = content.replace("PLACEHOLDER_PCNAME", pc_name)
content = content.replace("PLACEHOLDER_SERVER", server_url)

with open("tg_build.py", "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] tg_build.py created")
