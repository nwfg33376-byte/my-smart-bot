import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq
import json
import os
from datetime import datetime, timedelta

# ==========================================
# 1. استبدلي البيانات الأربع هنا ببياناتكِ الحقيقية:
TELEGRAM_TOKEN = "9209111321:AAG8XuVBdhy9dCtcvs0bLvvELDHZSxYoKzs"
GROQ_API_KEY = "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"
MY_IBAN = "SA058000022160801631"
ADMIN_ID = 1519768480
# ==========================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

system_instruction = """
أنت مساعد ذكي ومحاسب ومدير مبيعات محترف للمتاجر الإلكترونية في السعودية.
مهامك:
1. الرد على استفسارات الزبائن بلباقة وباللهجة السعودية البيضاء.
2. حساب أسعار المنتجات بدقة، جمع الفواتير، حساب الخصومات أو الضريبة فوراً.
3. مساعدة التاجر في صياغة ردود، تنظيم طلبات، أو أي مهمة حسابية وإدارية يطلبها.
4. كن سريعاً، دقيقاً، ومباشراً في إجاباتك.
"""

DATA_FILE = "all_merchants.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def ask_ai(user_text):
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_text}
        ]
    )
    return completion.choices[0].message.content

@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    user_id = str(message.chat.id)
    merchant_name = message.from_user.first_name
    
    markup = InlineKeyboardMarkup()
    btn = InlineKeyboardButton(f"✅ تفعيل 30 يوماً لـ {merchant_name}", callback_data=f"renew_{user_id}")
    markup.add(btn)
    
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.send_message(ADMIN_ID, f"💰 إيصال تحويل جديد من التاجر: {merchant_name}\nاضغطي الزر بالأسفل لتفعيل اشتراكه 30 يوماً:", reply_markup=markup)
    bot.reply_to(message, "⏳ تم استلام صورة الإيصال بنجاح، جاري التفعيل التلقائي خلال لحظات...")

@bot.callback_query_handler(func=lambda call: call.data.startswith("renew_"))
def activate_merchant(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    target_user_id = call.data.split("_")[1]
    data = load_data()
    new_expiry = datetime.now() + timedelta(days=30)
    data[target_user_id] = new_expiry.isoformat()
    save_data(data)
    
    bot.answer_callback_query(call.id, "تم التفعيل بنجاح!")
    bot.edit_message_text("✅ تم تفعيل اشتراك التاجر لمدة 30 يوماً بنجاح.", ADMIN_ID, call.message.message_id)
    bot.send_message(target_user_id, "🎉 تم تأكيد دفعتك وتفعيل اشتراكك لمدة 30 يوماً كاملة! البوت جاهز لخدمتك الآن.")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = str(message.chat.id)
    
    if message.chat.id == ADMIN_ID:
        try:
            bot.send_chat_action(message.chat.id, 'typing')
            reply = ask_ai(message.text)
            bot.reply_to(message, reply)
        except Exception as e:
            bot.reply_to(message, f"تنبيه تقني: {e}")
        return

    data = load_data()
    now = datetime.now()

    if user_id not in data:
        data[user_id] = (now + timedelta(days=1)).isoformat()
        save_data(data)
        bot.reply_to(message, "🎁 أهلاً بك! تم تفعيل تجربة مجانية لك لمدة 24 ساعة لتجربة ذكاء البوت.")

    expiry_date = datetime.fromisoformat(data[user_id])
    if now > expiry_date:
        bot.reply_to(
            message,
            f"⚠️ انتهت مدة التجربة أو الاشتراك الشهري.\n\n"
            f"للتفعيل الفوري لمدة 30 يوماً (1000 ريال)، حول المبلغ إلى الآيبان التالي:\n"
            f"`{MY_IBAN}`\n\n"
            f"📸 **ثم أرسل صورة الإيصال هنا مباشرة في المحادثة** وسيتم تفعيل البوت فوراً.",
            parse_mode="Markdown"
        )
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        reply = ask_ai(message.text)
        bot.reply_to(message, reply)
    except Exception:
        bot.reply_to(message, "أعد إرسال طلبك الآن وسأنفذه فوراً.")

print("البوت الموحد الذكي يعمل الآن 24/7...")
bot.infinity_polling(timeout=10, long_polling_timeout=5)
