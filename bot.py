import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq
from flask import Flask, request
import requests
import threading
import json
import os
from datetime import datetime, timedelta

# ==========================================
# 1. بياناتكِ الأساسية (توضع مرة واحدة في العمر)
TELEGRAM_TOKEN = "9209111321:AAG8XuVBdhy9dCtcvs0bLvvELDHZSxYoKzs"
GROQ_API_KEY = "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"
MY_IBAN = "SA058000022160801631"
ADMIN_ID = 1519768480
# ==========================================

app = Flask(__name__)
bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

DATA_FILE = "merchants_db.json"
user_states = {}

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    def ask_ai(user_text, store_info=""):
        system_prompt = "أنت موظف خدمة عملاء ومحاسب محترف لمتجر إلكتروني سعودي. تحدث باللهجة السعودية البيضاء بلباقة وسرعة. معلومات المتجر: " + str(store_info)
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]
    )
    return completion.choices[0].message.content

# ==========================================
# 2. استقبال رسائل الواتساب تلقائياً لجميع التجار المربوطين
@app.route('/whatsapp/<merchant_id>', methods=['POST'])
def whatsapp_webhook(merchant_id):
    data = load_data()
    if merchant_id not in data:
        return "Merchant not found", 404
    
    merchant = data[merchant_id]
    if datetime.now() > datetime.fromisoformat(merchant["expiry"]):
        return "Subscription expired", 403

    incoming = request.json
    try:
        msg_data = incoming.get("data", {})
        if msg_data.get("fromMe"):
            return "Ignored self message", 200
        
        customer_phone = msg_data.get("from")
        customer_text = msg_data.get("body", "")
        
        if customer_text and customer_phone:
            reply_text = ask_ai(customer_text, merchant.get("store_info", ""))
            instance_id = merchant.get("wa_instance")
            wa_token = merchant.get("wa_token")
            url = "https://api.ultramsg" + ".com/" + instance_id + "/messages/chat"
            requests.post(url, data={"token": wa_token, "to": customer_phone, "body": reply_text})
    except Exception as e:
        print("WA Error:", e)
    return "OK", 200

@app.route('/')
def home():
    return "Smart Multi-Merchant Bot (Telegram + WhatsApp) is Live!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# ==========================================
# 3. لوحة تحكم التاجر داخل تليجرام (تشرح له كل شيء ذاتياً)
def get_main_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🏪 إعداد منتجات وأسعار متجري", callback_data="set_store"),
        InlineKeyboardButton("📱 ربط البوت بالواتساب تلقائياً", callback_data="connect_wa"),
        InlineKeyboardButton("⏳ حالة اشتراكي", callback_data="check_sub")
    )
    return markup

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    user_id = str(message.chat.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {
            "expiry": (datetime.now() + timedelta(days=1)).isoformat(),
            "store_info": "",
            "wa_instance": "",
            "wa_token": ""
        }
        save_data(data)
    bot.reply_to(
        message,
        "👋 أهلاً بك في **المساعد الذكي للمتاجر**!\n"
        "يمكنك الآن إدارة متجرك، الرد على زبائنك في تليجرام والواتساب، وحساب الفواتير تلقائياً.\n\n"
        "اختر من القائمة بالأسفل أو اكتب طلبك مباشرة:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = str(call.from_user.id)
    data = load_data()

    if call.data == "set_store":
        user_states[user_id] = "WAITING_STORE_INFO"
        bot.send_message(user_id, "📝 أرسل الآن في رسالة واحدة **معلومات متجرك، قائمة المنتجات، الأسعار، وتكلفة الشحن** ليحفظها البوت ويرد على زبائنك بناءً عليها:")
    
    elif call.data == "connect_wa":
        user_states[user_id] = "WAITING_WA_DATA"
        webhook_link = "https://my-smart-bot-5uqf" + ".onrender" + ".com/whatsapp/" + user_id
        bot.send_message(
            user_id,
            f"📱 **دليل ربط رقمك في الواتساب بالبوت في 3 دقائق:**\n\n"
            f"1️⃣ ادخل على موقع بوابة الواتساب: Ultramsg.com وأنشئ حساباً.\n"
            f"2️⃣ اضغط **Create Instance** ثم امسح رمز **QR** بكاميرا واتساب جوالك لربط رقمك.\n"
            f"3️⃣ في نفس الصفحة ستجد خانة اسمها **Webhook URL**، انسخ هذا الرابط وضعه فيها ثم اضغط Save:\n"
            f"`{webhook_link}`\n\n"
            f"4️⃣ في أعلى الصفحة ستجد رقمين هما **Instance ID** و **Token**؛ انسخهما وأرسلهما لي هنا في رسالة واحدة وبينهما مسافة (مثال: `instance12345 token98765`):",
            parse_mode="Markdown"
        )

    elif call.data == "check_sub":
        expiry = datetime.fromisoformat(data[user_id]["expiry"])
        bot.send_message(user_id, f"📅 اشتراكك ساري حتى تاريخ:\n`{expiry.strftime('%Y-%m-%d %H:%M')}`", parse_mode="Markdown")

    elif call.data.startswith("renew_") and call.from_user.id == ADMIN_ID:
        target_id = call.data.split("_")[1]
        data[target_id]["expiry"] = (datetime.now() + timedelta(days=30)).isoformat()
        save_data(data)
        bot.edit_message_text("✅ تم تفعيل اشتراك التاجر 30 يوماً بنجاح.", ADMIN_ID, call.message.message_id)
        bot.send_message(target_id, "🎉 تم تأكيد دفعتك وتجديد اشتراكك لمدة 30 يوماً كاملة!")

@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    user_id = str(message.chat.id)
    name = message.from_user.first_name
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"✅ تفعيل 30 يوماً لـ {name}", callback_data=f"renew_{user_id}"))
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.send_message(ADMIN_ID, f"💰 إيصال جديد من: {name}", reply_markup=markup)
    bot.reply_to(message, "⏳ تم استلام الإيصال، سيتم التفعيل خلال لحظات...")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = str(message.chat.id)
    data = load_data()
    now = datetime.now()

    if user_id not in data:
        data[user_id] = {"expiry": (now + timedelta(days=1)).isoformat(), "store_info": "", "wa_instance": "", "wa_token": ""}
        save_data(data)

    if message.chat.id != ADMIN_ID and now > datetime.fromisoformat(data[user_id]["expiry"]):
        bot.reply_to(
            message,
            f"⚠️ انتهت مدة اشتراكك.\nللتجديد لمدة 30 يوماً (1000 ريال)، حول المبلغ إلى الآيبان:\n`{MY_IBAN}`\n📸 وأرسل صورة الإيصال هنا.",
            parse_mode="Markdown"
        )
        return

    state = user_states.get(user_id)
    if state == "WAITING_STORE_INFO":
        data[user_id]["store_info"] = message.text
        save_data(data)
        user_states[user_id] = None
        bot.reply_to(message, "✅ تم حفظ معلومات ومنتجات متجرك بنجاح! سأعتمد عليها الآن في الرد على زبائنك في تليجرام والواتساب.")
        return
    elif state == "WAITING_WA_DATA":
        parts = message.text.split()
        if len(parts) >= 2:
            data[user_id]["wa_instance"] = parts[0]
            data[user_id]["wa_token"] = parts[1]
            save_data(data)
            user_states[user_id] = None
            bot.reply_to(message, "✅ تم ربط رقمك في الواتساب بنجاح! البوت يرد الآن على زبائنك في الواتساب تلقائياً.")
        else:
            bot.reply_to(message, "⚠️ يرجى إرسال الـ Instance ID والتوكن وبينهما مسافة واحدة فقط.")
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        store_info = data[user_id].get("store_info", "")
        reply = ask_ai(message.text, store_info)
        bot.reply_to(message, reply)
    except Exception as e:
    bot.reply_to(message, f"السبب التقني: {e}")

print("البوت الشامل يعمل الآن 24/7...")
bot.infinity_polling(timeout=10, long_polling_timeout=5)
