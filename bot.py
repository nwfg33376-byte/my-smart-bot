import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq
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
STREAMPAY_API_KEY = "ضعي_مفتاح_STREAMPAY_هنا"

SUBSCRIPTION_PRICE = 1020  # 1020 ريال لتصلكِ 1000 ريال صافية في حسابكِ
INTERNAL_SERVER_URL = "https://pythonanywhere.com"
ADMIN_ID = 1519768480
# ==========================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)
DATA_FILE = "/home/Smartbots11/merchants_db.json"
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
# 2. الذكاء الاصطناعي الصارم (يمنع الأرقام والإيميلات المزورة)
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
        return completion.choices.message.content
    except Exception as e:
        print("AI Error:", e)
        return "عذراً، واجهت ضغطاً بسيطاً في النظام، أعد إرسال رسالتك بعد لحظات."

# ==========================================
# 3. بوابة الدفع الآلية StreamPay (بدون إظهار الآيبان)
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
        "metadata": {"merchant_id": str(merchant_id)}
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code in (200, 201):
            res_data = res.json()
            return res_data.get("payment_url") or res_data.get("url"), res_data.get("id")
    except Exception as e:
        print("StreamPay Error:", e)
    return None, None

def send_payment_prompt(user_id, merchant_name="تاجر"):
    pay_url, invoice_id = create_streampay_link(user_id, merchant_name)
    if invoice_id:
        data = load_data()
        if user_id in data:
            data[user_id]["last_invoice_id"] = invoice_id
            save_data(data)

    markup = InlineKeyboardMarkup(row_width=1)
    if pay_url:
        markup.add(InlineKeyboardButton(f"💳 ادفع الآن ({SUBSCRIPTION_PRICE} ريال) عبر البطاقة", url=pay_url))
    markup.add(InlineKeyboardButton("✅ تم الدفع — تفعيل اشتراكي الآن", callback_data="verify_payment"))

    msg = (
        "⚠️ **انتهت مدة تجربتك / اشتراكك الحالي!**\n\n"
        "لتفعيل البوت لمتجرك لمدة **30 يوماً كاملة**، اضغط على زر الدفع بالأسفل.\n"
        f"💰 **قيمة الاشتراك الشهري:** `{SUBSCRIPTION_PRICE} ريال سعودي` (شاملة رسوم الدفع الإلكتروني).\n\n"
        "⚡ **بعد إتمام الدفع بالبطاقة، سيتفعل اشتراكك تلقائياً خلال ثوانٍ!**"
    )
    try:
        bot.send_message(user_id, msg, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print("Send Payment Error:", e)

def verify_invoice_paid(invoice_id):
    if not invoice_id:
        return False
    url = f"https://streampay.sa/{invoice_id}"
    headers = {"Authorization": f"Bearer {STREAMPAY_API_KEY}"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            status = str(res.json().get("status", "")).lower()
            return status in ("paid", "succeeded", "completed")
    except Exception:
        pass
    return False

# ==========================================
# 4. مراقب الاشتراكات + قارئ رسائل الواتساب في الخلفية
def background_worker():
    while True:
        try:
            data = load_data()
            now = datetime.now()
            changed = False

            for uid, info in data.items():
                expiry = datetime.fromisoformat(info["expiry"])

                # 1. التحقق الآلي من الفواتير المدفوعة في StreamPay
                if now > expiry and info.get("last_invoice_id"):
                    if verify_invoice_paid(info["last_invoice_id"]):
                        new_expiry = datetime.now() + timedelta(days=30)
                        data[uid]["expiry"] = new_expiry.isoformat()
                        data[uid]["notified_expired"] = False
                        data[uid]["last_invoice_id"] = ""
                        changed = True
                        try:
                            bot.send_message(
                                uid,
                                f"🎉 **تم تأكيد دفعتك وتفعيل اشتراكك لمدة 30 يوماً كاملة تلقائياً!**\n"
                                f"📅 **ينتهي اشتراكك القادم في:** `{new_expiry.strftime('%Y-%m-%d الساعة %H:%M')}`",
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                        continue

                # 2. إرسال تنبيه انتهاء الاشتراك تلقائياً فور انتهاء الوقت
                if now > expiry and not info.get("notified_expired", False):
                    send_payment_prompt(uid, info.get("name", "تاجر"))
                    data[uid]["notified_expired"] = True
                    changed = True

                # 3. استقبال والرد على رسائل الواتساب لكل تاجر نشط (معزول 100%)
                if now <= expiry and info.get("wa_instance") and info.get("wa_token"):
                    id_inst = info["wa_instance"]
                    wa_tok = info["wa_token"]
                    rec_url = f"https://green-api.com{id_inst}/receiveNotification/{wa_tok}"
                    res = requests.get(rec_url, timeout=5)
                    if res.status_code == 200 and res.json():
                        notif = res.json()
                        receipt_id = notif.get("receiptId")
                        body = notif.get("body", {})
                        if body.get("typeWebhook") == "incomingMessageReceived":
                            sender = body.get("senderData", {}).get("chatId", "")
                            text = body.get("messageData", {}).get("textMessageData", {}).get("textMessage", "")
                            if text and sender and not sender.endswith("@g.us"):
                                reply_text = ask_ai(text, info.get("store_info", ""))
                                send_url = f"https://green-api.com{id_inst}/sendMessage/{wa_tok}"
                                requests.post(send_url, json={"chatId": sender, "message": reply_text}, timeout=10)
                        if receipt_id:
                            del_url = f"https://green-api.com{id_inst}/deleteNotification/{wa_tok}/{receipt_id}"
                            requests.delete(del_url, timeout=5)

            if changed:
                save_data(data)
        except Exception as e:
            print("Worker Error:", e)
        time.sleep(3)

threading.Thread(target=background_worker, daemon=True).start()

# ==========================================
# 5. واجهة البوت في تيليجرام
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
            "last_invoice_id": "",
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
        "اختر من القائمة بالأسفل:",
        reply_markup=get_main_menu(),
