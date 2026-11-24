import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq
from flask import Flask, request
import requests
import json
import os
import threading
import time
from datetime import datetime, timedelta

# ==========================================
# 1. إعداداتكِ الأساسية (ضعي مفاتيحكِ هنا)
TELEGRAM_TOKEN = "9209111321:AAHvZ3B5KUUK0aeZBVCUtu9vKnVnU9tGID8"
GROQ_API_KEY = "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"

# بيانات بوابة الدفع StreamPay (ستريم باي)
STREAMPAY_API_KEY = "ضعي_مفتاح_STREAMPAY_هنا"
SUBSCRIPTION_PRICE = 1020  # 1020 ريال لتصلكِ 1000 ريال صافية في حسابكِ بعد رسوم مدى

# رابط سيرفركِ الداخلي (مخفي تماماً عن التجار)
INTERNAL_SERVER_URL = "https://pythonanywhere.com"
ADMIN_ID = 1519768480
# ==========================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)

DATA_FILE = "merchants_db.json"
user_states = {}
db_lock = threading.Lock()

def load_data():
    with db_lock:
        if not os.path.exists(DATA_FILE):
            return {}
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

def save_data(data):
    with db_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 2. الذكاء الاصطناعي المنضبط (يمنع الأرقام والإيميلات المزورة)
def ask_ai(user_text, store_info=""):
    if not store_info.strip():
        return "أهلاً بك! المتجر قيد التجهيز حالياً، يرجى ترك رسالتك وسنرد عليك في أقرب وقت."

    system_prompt = (
        "أنت موظف خدمة عملاء ومحاسب محترف لمتجر إلكتروني سعودي. أجب باختصار شديد ولباقة وباللهجة السعودية البيضاء.\n"
        "قواعد صارمة لا يمكن تجاوزها أبداً:\n"
        "1. اعتمد حصرياً وبنسبة 100% على (معلومات المتجر المعتمدة) بالأسفل فقط.\n"
        "2. يُمنع منعاً باتاً اختراع أو تخمين أو كتابة أي رقم جوال، رقم واتساب، بريد إلكتروني، رابط، حساب بنكي، أو سعر غير مذكور حرفياً في معلومات المتجر.\n"
        "3. إذا طلب العميل رقم تواصل، إيميل، رابط، أو سأل عن منتج غير مذكور بالأسفل، أجب بهذه الجملة فقط ولا تضف عليها شيئاً: "
        "«للتواصل المباشر مع إدارة المتجر أو الاستفسار عن تفاصيل إضافية، يرجى ترك رسالتك هنا وسنرد عليك في أقرب وقت.»\n\n"
        "معلومات المتجر المعتمدة:\n" + str(store_info)
    )
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        print("AI Error:", e)
        return "عذراً، واجهت ضغطاً بسيطاً في النظام، أعد إرسال رسالتك بعد لحظات."

# ==========================================
# 3. إنشاء رابط دفع تلقائي عبر StreamPay (بدون إظهار الآيبان)
def create_streampay_link(merchant_id, merchant_name):
    url = "https://streampay.sa"
    headers = {
        "Authorization": f"Bearer {STREAMPAY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": SUBSCRIPTION_PRICE,
        "currency": "SAR",
        "description": f"اشتراك شهري (30 يوم) - المساعد الذكي للمتاجر ({merchant_name})",
        "callback_url": f"{INTERNAL_SERVER_URL}/streampay_webhook",
        "metadata": {
            "merchant_id": str(merchant_id)
        }
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code in (200, 201):
            res_data = res.json()
            return res_data.get("payment_url") or res_data.get("url")
    except Exception as e:
        print("StreamPay Error:", e)
    return None

def send_payment_prompt(user_id, merchant_name="تاجر"):
    pay_url = create_streampay_link(user_id, merchant_name)
    markup = InlineKeyboardMarkup()
    if pay_url:
        markup.add(InlineKeyboardButton(f"💳 ادفع الآن ({SUBSCRIPTION_PRICE} ريال) وفعّل شهرك تلقائياً", url=pay_url))
    else:
        markup.add(InlineKeyboardButton("🔄 تحديث رابط الدفع", callback_data="check_sub"))

    msg = (
        "⚠️ **انتهت مدة تجربتك / اشتراكك الحالي!**\n\n"
        "لتفعيل البوت لمتجرك لمدة **30 يوماً كاملة**، اضغط على زر الدفع بالأسفل.\n"
        f"💰 **قيمة الاشتراك الشهري:** `{SUBSCRIPTION_PRICE} ريال سعودي` (شاملة رسوم الدفع الإلكتروني).\n\n"
        "⚡ **بمجرد إتمام الدفع بالبطاقة (مدى / فيزا / Apple Pay)، سيتفعل اشتراكك تلقائياً في نفس الثانية!**"
    )
    try:
        bot.send_message(user_id, msg, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print("Send Payment Prompt Error:", e)

# استقبال إشعار الدفع الناجح من StreamPay وتفعيل الـ 30 يوماً تلقائياً
@app.route('/streampay_webhook', methods=['POST'])
def streampay_webhook():
    payload = request.json or {}
    status = str(payload.get("status", "")).lower()
    metadata = payload.get("metadata", {})
    merchant_id = str(metadata.get("merchant_id", ""))

    if status in ("paid", "succeeded", "completed") and merchant_id:
        data = load_data()
        if merchant_id in data:
            new_expiry = datetime.now() + timedelta(days=30)
            data[merchant_id]["expiry"] = new_expiry.isoformat()
            data[merchant_id]["notified_expired"] = False
            save_data(data)
            try:
                bot.send_message(
                    merchant_id,
                    f"🎉 **تم استلام دفعتك وتفعيل اشتراكك لمدة 30 يوماً كاملة تلقائياً!**\n"
                    f"📅 **ينتهي اشتراكك القادم في:** `{new_expiry.strftime('%Y-%m-%d الساعة %H:%M')}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
    return "OK", 200

# ==========================================
# 4. فحص تلقائي في الخلفية لإرسال تنبيه الدفع فور انتهاء الوقت
def subscription_watcher():
    while True:
        try:
            data = load_data()
            now = datetime.now()
            changed = False
            for uid, info in data.items():
                expiry = datetime.fromisoformat(info["expiry"])
                if now > expiry and not info.get("notified_expired", False):
                    send_payment_prompt(uid, info.get("name", "تاجر"))
                    data[uid]["notified_expired"] = True
                    changed = True
            if changed:
                save_data(data)
        except Exception as e:
            print("Watcher Error:", e)
        time.sleep(60)  # يفحص كل دقيقة

threading.Thread(target=subscription_watcher, daemon=True).start()

# ==========================================
# 5. ربط واستقبال رسائل الواتساب (معزول لكل تاجر بدقة 100%)
def configure_whatsapp_webhook(id_instance, api_token, merchant_id):
    # نضبط الرابط في الخلفية تلقائياً دون أن يراه التاجر
    api_url = f"https://green-api.com{id_instance}/setSettings/{api_token}"
    webhook_url = f"{INTERNAL_SERVER_URL}/whatsapp/{merchant_id}"
    payload = {
        "webhookUrl": webhook_url,
        "incomingWebhook": "yes"
    }
    try:
        res = requests.post(api_url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception:
        return False

@app.route('/whatsapp/<merchant_id>', methods=['POST'])
def whatsapp_webhook(merchant_id):
    data = load_data()
    if merchant_id not in data:
        return "Merchant not found", 404

    merchant = data[merchant_id]
    # إيقاف الرد التلقائي إذا انتهى اشتراك التاجر
    if datetime.now() > datetime.fromisoformat(merchant["expiry"]):
        return "Subscription expired", 403

    incoming = request.json or {}
    try:
        if incoming.get("typeWebhook") == "incomingMessageReceived":
            sender_data = incoming.get("senderData", {})
            message_data = incoming.get("messageData", {})
            customer_chat_id = sender_data.get("chatId")
            customer_text = message_data.get("textMessageData", {}).get("textMessage", "")

            if customer_text and customer_chat_id and not customer_chat_id.endswith("@g.us"):
                # يقرأ معلومات متجر هذا التاجر فقط (عزل تام)
                reply_text = ask_ai(customer_text, merchant.get("store_info", ""))
                id_inst = merchant.get("wa_instance")
                wa_tok = merchant.get("wa_token")
                if id_inst and wa_tok:
                    send_url = f"https://green-api.com{id_inst}/sendMessage/{wa_tok}"
                    requests.post(send_url, json={"chatId": customer_chat_id, "message": reply_text}, timeout=10)
    except Exception as e:
        print("WA Webhook Error:", e)
    return "OK", 200

# ==========================================
# 6. واجهة البوت في تليجرام
def get_main_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🏪 إعداد منتجات وأسعار متجري", callback_data="set_store"),
        InlineKeyboardButton("📱 ربط البوت بالواتساب تلقائياً", callback_data="connect_wa"),
        InlineKeyboardButton("⏳ حالة اشتراكي وتاريخ الانتهاء", callback_data="check_sub")
    )
    return markup

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    user_id = str(message.chat.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {
            "name": message.from_user.first_name or "تاجر",
            "expiry": (datetime.now() + timedelta(hours=24)).isoformat(),
            "notified_expired": False,
            "store_info": "",
            "wa_instance": "",
            "wa_token": ""
        }
        save_data(data)

    bot.reply_to(
        message,
        "👋 أهلاً بك في **المساعد الذكي للمتاجر**!\n"
        "يمكنك الآن إدارة متجرك، الرد على زبائنك بذكاء، وحساب الفواتير تلقائياً.\n\n"
        "🎁 لديك **24 ساعة تجربة مجانية** كاملة، وبعدها يتجدد الاشتراك شهرياً بـ **1020 ريال**.\n\n"
