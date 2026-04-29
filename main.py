import os, logging, secrets, psycopg2, asyncio, threading
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- 1. قاموس اللغات (Translations) ---
STRINGS = {
    'العربية': {
        'main_menu': "🏠 القائمة الرئيسية لبوت <b>Mr.MHO</b>",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n🆔 معرفك: <code>{uid}</code>\n🔑 التوكن: <code>{token}</code>",
        'no_channels': "❌ لم تقم بإضافة أي قنوات بعد.",
        'webhooks_title': "🌐 <b>روابط الويب هوك الخاصة بك:</b>",
        'lang_success': "✅ تم تغيير اللغة إلى: <b>العربية</b>",
        'ask_order': "📝 <b>الرجاء إرسال رقم الطلب الخاص بك الآن:</b>",
        'gen_token_err': "⚠️ <b>عذراً!</b> يجب إضافة قناة أولاً لتوليد رمز.",
        'gen_token_ok': "🔄 <b>تم تحديث رمز الأمان!</b>\n🔑 الرمز الجديد: <code>{token}</code>",
        'set_k_prompt': "📝 أرسل Alpaca Key ID:",
        'set_s_prompt': "📝 أرسل Alpaca Secret Key:",
        'add_ch_prompt': "📢 أرسل ID القناة أو المجموعة (مثال: -100xxx):",
        'buy_title': "💎 <b>تفعيل الاشتراك المميز</b>\nاستخدم الرابط أدناه للاشتراك، ثم أرسل رقم الطلب هنا.",
        'alpaca_title': "🚀 <b>إعدادات Alpaca:</b>\nاضبط مفاتيح التداول الآلي الخاص بك.",
        'del_title': "❌ اختر القناة المراد إزالتها:"
    },
    'English': {
        'main_menu': "🏠 <b>Mr.MHO</b> Main Menu",
        'acc_info': "👤 <b>Your Account:</b>\n🆔 ID: <code>{uid}</code>\n🔑 Token: <code>{token}</code>",
        'no_channels': "❌ No channels added yet.",
        'webhooks_title': "🌐 <b>Your Webhook URLs:</b>",
        'lang_success': "✅ Language changed to: <b>English</b>",
        'ask_order': "📝 <b>Please send your Order ID now:</b>",
        'gen_token_err': "⚠️ <b>Sorry!</b> Add a channel first to generate a token.",
        'gen_token_ok': "🔄 <b>Security token updated!</b>\n🔑 New Token: <code>{token}</code>",
        'set_k_prompt': "📝 Send your Alpaca Key ID:",
        'set_s_prompt': "📝 Send your Alpaca Secret Key:",
        'add_ch_prompt': "📢 Send Channel/Group ID (e.g., -100xxx):",
        'buy_title': "💎 <b>Premium Subscription</b>\nUse the link to subscribe, then send your Order ID.",
        'alpaca_title': "🚀 <b>Alpaca Settings:</b>\nConfigure your trading keys.",
        'del_title': "❌ Select channel to remove:"
    }
}

# --- 2. الإعدادات ---
DB_URL = "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 8711658382
DOMAIN = "https://moh-signalsbot.up.railway.app"

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# إعداد مجمع الاتصالات
try:
    db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)
    logging.info("✅ Database pool connected")
except Exception as e:
    logging.error(f"❌ DB Pool Error: {e}")

def get_db_conn(): return db_pool.getconn()
def release_db_conn(conn): db_pool.putconn(conn)

# --- 3. الدوال المساعدة وقاعدة البيانات ---
async def get_user_data(uid):
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            user = cur.fetchone()
            if not user:
                # إنشاء مستخدم جديد إذا لم يوجد
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token, language) VALUES (%s, %s, %s) RETURNING *", 
                            (uid, token, 'العربية'))
                conn.commit()
                user = cur.fetchone()
            return user
    finally:
        if conn: release_db_conn(conn)

async def get_main_menu(lang):
    if lang == 'English':
        buttons = [
            [InlineKeyboardButton("👤 Account", callback_data='acc'), InlineKeyboardButton("🛒 Activate", callback_data='buy')],
            [InlineKeyboardButton("📢 Add Channel", callback_data='add_channel'), InlineKeyboardButton("📺 My Channels", callback_data='my_channels')],
            [InlineKeyboardButton("❌ Remove Channel", callback_data='del_menu')],
            [InlineKeyboardButton("🌐 Webhooks", callback_data='url'), InlineKeyboardButton("🔄 New Token", callback_data='gen_token')],
            [InlineKeyboardButton("🌍 Language", callback_data='change_lang'), InlineKeyboardButton("🚀 Alpaca", callback_data='alpaca')],
            [InlineKeyboardButton("☎️ Support", url=f'tg://user?id={ADMIN_ID}')]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')],
            [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📺 قنواتي", callback_data='my_channels')],
            [InlineKeyboardButton("❌ إزالة قناة", callback_data='del_menu')],
            [InlineKeyboardButton("🌐 روابط الويب هوك", callback_data='url'), InlineKeyboardButton("🔄 رمز أمان جديد", callback_data='gen_token')],
            [InlineKeyboardButton("🌍 تغيير اللغة", callback_data='change_lang'), InlineKeyboardButton("🚀 التداول الآلي", callback_data='alpaca')],
            [InlineKeyboardButton("☎️ الدعم", url=f'tg://user?id={ADMIN_ID}')]
        ]
    return InlineKeyboardMarkup(buttons)

# --- 4. معالجة الرسائل والأزرار (المدمجة) ---
# [هنا تضع دوال handle_message و button_callback التي رتبناها سابقاً]
# تأكد من استخدام get_db_conn() و release_db_conn(conn) داخلها.

if __name__ == "__main__":
    # تشغيل Flask في خيط منفصل (Thread) لاستقبال الويب هوك
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)).start()
    
    # تشغيل البوت
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    # إضافة handlers هنا (CommandHandler, CallbackQueryHandler, الخ)
    application.run_polling()
