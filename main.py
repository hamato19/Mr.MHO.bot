import os
import logging
import secrets
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import threading

# --- الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def get_db():
    return psycopg2.connect(DB_URL)

# --- جلب بيانات المستخدم ---
async def get_user_data(uid):
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            user = cur.fetchone()
            if not user:
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
                conn.commit()
                user = {"user_id": uid, "secret_token": token}
        conn.close()
        return user
    except Exception as e:
        logging.error(f"DB Error: {e}")
        return None

# --- اللوحة الرئيسية ---
async def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')],
        [InlineKeyboardButton("📺 قنواتي", callback_data='my_channels'), InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel')],
        [InlineKeyboardButton("💬 إضافة مجموعة", callback_data='add_group'), InlineKeyboardButton("❌ إزالة قناة", callback_data='del_entity')],
        [InlineKeyboardButton("🔄 توليد رمز أمان", callback_data='gen_token'), InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='url')],
        [InlineKeyboardButton("▶️ طريقة الاستخدام", callback_data='help')],
        [InlineKeyboardButton("🚀 التداول الآلي 🤖", callback_data='alpaca')],
        [InlineKeyboardButton("☎️ الدعم", callback_data='support')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- معالج الأزرار ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    u = await get_user_data(uid)
# --- إضافة كود زر حسابي هنا ---
    if query.data == 'acc':
        # 1. جلب بيانات المستخدم الأساسية والاشتراك
      u = await get_user_data(uid)  
        # 2. حساب عدد القنوات المربوطة من جدول entities في Neon
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (uid,))
        channels_count = cur.fetchone()[0]
        cur.close()
        conn.close()

        # 3. صياغة رسالة الحساب الاحترافية بالبيانات من قاعدة البيانات
        account_msg = (
            f"👤 <b>معلومات حسابك الشخصي</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🆔 <b>معرف المستخدم:</b> <code>{uid}</code>\n"
            f"📺 <b>القنوات المفعلة:</b> {channels_count} قناة\n"
            f"⏳ <b>أيام الاشتراك:</b> {u.get('subscription_days', 0)} يوم\n"
            f"📊 <b>إشارات متبقية:</b> {u.get('remaining_signals', 0)}\n"
            f"💰 <b>إجمالي المدفوع:</b> ${u.get('total_paid', 0.00):.2f}\n"
            f"━━━━━━━━━━━━━━━"
        )
        
        await query.edit_message_text(
            text=account_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=await get_main_menu()
        )
            elif query.data == 'buy':
        # أزرار خيارات الاشتراك
        keyboard = [
            [InlineKeyboardButton("💳 إرسال رقم الطلب", callback_data='submit_order')],
            [InlineKeyboardButton("👨‍💻 التواصل مع الدعم للطلب", url='https://t.me/YOUR_ADMIN_USERNAME')],
            [InlineKeyboardButton("🔙 العودة للرئيسية", callback_data='back_home')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🛒 <b>قسم تفعيل الاشتراك</b>\n\n"
            "يمكنك تفعيل اشتراكك بإحدى الطريقتين:\n"
            "1️⃣ إذا كان لديك رقم طلب سابق، اضغط على <b>إرسال رقم الطلب</b>.\n"
            "2️⃣ للطلب الجديد أو الاستفسار، اضغط على <b>التواصل مع الدعم</b> وسيتم تحويلك للمسؤول.",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    if query.data == 'url':
        # التحقق من Neon: هل توجد قنوات؟
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
        has_entity = cur.fetchone()
        conn.close()

        if has_entity:
            webhook_url = f"https://mr-mho-bot.onrender.com/webhook/{u['secret_token']}"
            await query.edit_message_text(f"🌐 <b>رابط الويب هوك الخاص بك:</b>\n\n<code>{webhook_url}</code>", 
                                          parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())
        else:
            await query.edit_message_text("⚠️ <b>تنبيه:</b> يجب ربط قناة أو مجموعة أولاً لتفعيل الويب هوك.", 
                                          reply_markup=await get_main_menu())

    elif query.data in ['add_channel', 'add_group']:
        is_ch = (query.data == 'add_channel')
        req_id = 1 if is_ch else 2
        kb = [[KeyboardButton(f"🔗 اضغط هنا للربط", request_chat=KeyboardButtonRequestChat(request_id=req_id, chat_is_channel=is_ch))]]
        await context.bot.send_message(chat_id=uid, text="يرجى اختيار الكيان المراد ربطه:", 
                                       reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

    elif query.data == 'my_channels':
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT entity_id, random_tag FROM entities WHERE user_id = %s", (uid,))
        rows = cur.fetchall()
        conn.close()
        msg = "📺 <b>قنواتك المربوطة:</b>\n\n" + "\n".join([f"🔹 {r[0]} | Tag: {r[1]}" for r in rows]) if rows else "❌ لا توجد قنوات."
        await query.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())

# --- حفظ بيانات الربط ---
async def handle_entity_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared = update.message.chat_shared if update.message.chat_shared else update.message.user_shared
    uid = update.effective_user.id
    eid = str(shared.chat_id)
    rtag = secrets.token_hex(4).upper()
    
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO entities (user_id, entity_id, random_tag) VALUES (%s, %s, %s)
            ON CONFLICT (entity_id) DO UPDATE SET user_id = EXCLUDED.user_id, random_tag = EXCLUDED.random_tag
        """, (uid, eid, rtag))
        conn.commit(); cur.close(); conn.close()
        await update.message.reply_text(f"✅ تم الربط بنجاح!\nID: {eid}", reply_markup=await get_main_menu())
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً بك في لوحة تحكم Mr.MOH 🤖", reply_markup=await get_main_menu())

@app.route('/')
def index(): return "Online"

if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_entity_shared))
    application.run_polling()
