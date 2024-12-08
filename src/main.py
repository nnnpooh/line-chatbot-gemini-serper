import http.client
import json
import os
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from flask import Flask, abort, request
from google.ai.generativelanguage_v1beta.types import content
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

load_dotenv()  # take environment variables from .env.

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN")
GEMINI_TOKEN = os.getenv("GEMINI_TOKEN")
SERPER_TOKEN = os.getenv("SERPER_TOKEN")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
generation_config_schema = {
    "temperature": 0.25,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_schema": content.Schema(
        type=content.Type.OBJECT,
        enum=[],
        required=["response", "search_required"],
        properties={
            "response": content.Schema(
                type=content.Type.STRING,
                description="Direct response to the query if known",
            ),
            "search_required": content.Schema(
                type=content.Type.BOOLEAN,
                description="Whether additional internet search is needed",
            ),
            "search_query": content.Schema(
                type=content.Type.STRING,
                description="Refined search query if search is required",
            ),
            "confidence_level": content.Schema(
                type=content.Type.NUMBER,
                description="Confidence of the current response (0-1)",
            ),
        },
    ),
    "response_mime_type": "application/json",
}
# Create the model
generation_config_default = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}


def ai_response(question: str):
    genai.configure(api_key=GEMINI_TOKEN)  #### Insert Your API KEY
    # Create the model

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config_schema,
        system_instruction="You are a chat-bot name 'Chotipon - Bot' to be communate aisstance that provide my intel to user, if you cant answer it from detail you have, tell them that it out of your knowledge, some part or question can be answer informal, but keep it polite",
    )

    chat_session = model.start_chat(
        history=[
            {
                "role": "user",
                "parts": [
                    ' โดยรู้รายละเอียดข้อมูลมีดังนี้ ชื่อ : นายโชติพล ภักดีธรรมะสกุล\\nเกิดวันที่ : 27/07/1998\\nการศึกษา : ปริญญาตรี สาขาวิชา วิศวกรรมอุตสาหการ คณะวิศวกรรมศาสตร์ มหาวิทยาลัยเชียงใหม่, มหาบัณฑิต สาขาวิชา วิศวกรรมอุตสาหการ คณะวิศวกรรมศาสตร์ มหาวิทยาลัยเชียงใหม่\\nช่องทางการติดต่อ : TEL: 061-906-4490, Email: Chotipon.pd@gmail.com\\nการทำงานปัจจุบัน : ทำงานในตำแหน่ง Data Scientist อยู่ที่ PDKM (https://www.pdkm.tech/)\\n\\nจากข้อมูลข้างต้นช่วยคอบอย่างเป็นทางการ, กระชับ, สั้น, ได้ใจความ และสุภาพ\\nช่วยฉันตอบคำถามให้หน่อย แต่ถ้าไม่สามารถตอบได้ให้ตอบว่า แต่สามารถเป็นตัวช่วยในการหาข้อมูลจากอินเตอร์เน็ตได้ แต่ถ้าไม่มีความเกียวข้องหรือสามารถตอบได้ ให้ตอบว่า \\"อยู่นอกเหนือข้อมูลที่มี\\" \\n '
                ],
            }
        ]
    )

    response = chat_session.send_message(question)

    resp_dict = json.loads(response.text)
    if resp_dict["search_required"] == True:
        conn = http.client.HTTPSConnection("google.serper.dev")
        payload = json.dumps({"q": resp_dict.get("search_query")})
        headers = {"X-API-KEY": SERPER_TOKEN, "Content-Type": "application/json"}
        conn.request("POST", "/search", payload, headers)
        res = conn.getresponse()
        data = res.read()

        data_dict = json.loads(data.decode("utf-8"))

        ops = [i.get("snippet") for i in data_dict["organic"]]

        ops_str = ", ".join(ops)

        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config_default,
            system_instruction="You are a chat-bot that provide my intel to user, if you cant answer it from detail you have, tell them that it out of your knowledge, some part or question can be answer informal, but keep it polite",
        )

        chat_session = model.start_chat(
            history=[
                {
                    "role": "user",
                    "parts": [
                        f"สรุปข้อมูลดังต่อไปนี้ให้เข้าใจง่าย และน่าสนใจออกมา จากข้อมูลการค้นหาดังนี้ {ops_str} โดยมีรายละเอียดอยู่บ้าง"
                    ],
                }
            ]
        )

        response = chat_session.send_message("สรุปข้อมูล")

        output = response.text
    else:
        output = resp_dict["response"]
    return output


app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def callback():
    # get X-Line-Signature header value
    signature = request.headers["X-Line-Signature"]

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info(
            "Invalid signature. Please check your channel access token/channel secret."
        )
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    resp_to_user = ai_response(event.message.text)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token, messages=[TextMessage(text=resp_to_user)]
            )
        )


# https://github.com/alexdlaird/pyngrok
from pyngrok import conf, ngrok


def log_event_callback(log):
    print(str(log))


conf.get_default().log_event_callback = log_event_callback
conf.get_default().region = "jp"

NGROK_REGION = "ap"

conf.get_default().auth_token = NGROK_AUTHTOKEN
conf.get_default().region = NGROK_REGION

# Open a HTTP tunnel on the port 5000
# <NgrokTunnel: "http://<public_sub>.ngrok.io" -> "http://localhost:5000">
http_tunnel = ngrok.connect(5000)
print(http_tunnel)


def setWebhook(endpoint, CHANNEL_ACCESS_TOKEN):
    endpointFixed = "https://" + endpoint.split("//")[-1] + "/webhook"
    url = "https://api.line.me/v2/bot/channel/webhook/endpoint"
    header = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + CHANNEL_ACCESS_TOKEN,
    }
    body = json.dumps({"endpoint": endpointFixed})
    response = requests.put(url=url, data=body, headers=header)
    print(response)
    obj = json.loads(response.text)
    print(obj)


setWebhook(http_tunnel.public_url, LINE_CHANNEL_ACCESS_TOKEN)

app.run()


# tunnels=ngrok.get_tunnels()
# [ngrok.disconnect(i.public_url) for i in tunnels]
