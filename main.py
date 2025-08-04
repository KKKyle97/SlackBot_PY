import os
import requests
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from dotenv import load_dotenv
from langdetect import detect

load_dotenv()

FLAG_LANG_MAP = {
    'flag-jp': 'JA',
    'flag-kr': 'KO',
    'flag-cn': 'ZH',
    'flag-us': 'EN'
}

glossary_list = []

app = App(
    token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET")
)

flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

def get_all_glossaries():
    try:
        headers = {
            'Authorization': f'DeepL-Auth-Key {os.getenv("DEEPL_API_KEY")}'
        }
        response = requests.get('https://api-free.deepl.com/v3/glossaries', headers=headers)
        return response.json().get("glossaries", [])
    except:
        return []

def translate_text(text, source_lang=None, target_lang="EN"):
    url = "https://api-free.deepl.com/v2/translate"
    params = {
        "auth_key": os.getenv("DEEPL_API_KEY"),
        "text": text,
        "target_lang": target_lang
    }
    if source_lang:
        params["source_lang"] = source_lang
    if glossary_list:
        params["glossary_id"] = glossary_list[0]["glossary_id"]
    res = requests.post(url, params=params)
    data = res.json()["translations"][0]
    return {
        "translated_text": data["text"],
        "detected_source_lang": data.get("detected_source_language")
    }

@app.event("reaction_added")
def handle_reaction_added(body, client, event):
    emoji_key = "flag-" + event["reaction"]
    target_lang = FLAG_LANG_MAP.get(emoji_key)
    if not target_lang:
        return

    channel_id = event["item"]["channel"]
    message_ts = event["item"]["ts"]

    result = client.conversations_history(
        channel=channel_id,
        latest=message_ts,
        inclusive=True,
        limit=1
    )
    original_text = result["messages"][0].get("text", "")
    if not original_text.strip():
        return

    detected_lang = detect(original_text).upper()
    if detected_lang == target_lang:
        return

    result = translate_text(original_text, source_lang=detected_lang, target_lang=target_lang)

    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        text=f"🌐 *Translated ({target_lang}):*\n{result['translated_text']}"
    )

# This endpoint is required for Slack Events API to verify the endpoint
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

if __name__ == "__main__":
    glossary_list = get_all_glossaries()
    flask_app.run(port=int(os.getenv("PORT", 3000)))
