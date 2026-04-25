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

# --- فحص هل المستخدم لديه قنوات مرتبطة ---
async def check_user_entities(uid):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (uid,))
            count = cur.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        logging.error(f"Error checking entities: {e}")
        return False

# --- جلب بيانات المستخدم ---
async def get_user_data(uid):
    user = {"user_id": uid, "lang": "ar"}
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            result = cur.fetchone()
            if not result:
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
                conn.commit()
                user = {"user_id": uid, "secret_token": token, "lang": "ar"}
            else:
                user = result
        conn.close()
    except Exception as e:
        logging.error(f"DB Error: {e}")
    return user

# --- القائمة الرئيسية (Inline Only) ---
async def get_main_menu(u):
    inline_kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')],
        [InlineKeyboardButton("📺 قنواتي", callback_data='my_entities'), InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel')],
        [InlineKeyboardButton("💬 إضافة مجموعة", callback_data='add_group'), InlineKeyboardButton("❌ إزالة قناة/مجموعة", callback_data='del_entity')],
        [InlineKeyboardButton("🔄 توليد رمز أمان", callback_data='gen_token'), InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='url')],
        [InlineKeyboardButton("▶️ طريقة الاستخدام", callback_data='help'), InlineKeyboardButton("🌍 تغيير اللغة", callback_data='lang')],
        [InlineKeyboardButton("🚀 التداول الآلي 🤖", callback_data='alpaca')],
        [InlineKeyboardButton("☎️ الدعم", callback_data='support')]
    ]
    return InlineKeyboardMarkup(inline_kb)

# --- معالج ضغطات الأزرار ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    u = await get_user_data(uid)

    if query.data == 'url':
        # المنطق المطلوب: فحص الربط قبل إعطاء الرابط
        has_entity = await check_user_entities(uid)
        if has_entity:
            webhook_url = f"https://mr-mho-bot.onrender.com/webhook/{u.get('secret_token')}"
            await query.edit_message_text(
                f"🌐 <b>رابط الويب هوك الخاص بك جاهز:</b>\n\n<code>{webhook_url}</code>\n\n"
                f"تأكد من إرسال الإشارات لهذا الرابط ليتم توجيهها لقناتك.",
                parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(u)
            )
        else:
            await query.edit_message_text(
                "⚠️ <b>عذراً، لم تقم بربط أي قناة أو مجموعة بعد!</b>\n\n"
                "يجب إضافة قناة أولاً وتفعيل البوت فيها كمشرف لتتمكن من استخدام الويب هوك.",
                parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(u)
            )

    elif query.data in ['add_channel', 'add_group']:
        # حذفنا الأزرار السفلية واستبدلناها برسالة تطلب الضغط على زر الربط الرسمي
        is_channel = (query.data == 'add_channel')
        req_id = 1 if is_channel else 2
        label = "قناة" if is_channel else "مجموعة"
        
        # نستخدم زر ReplyKeyboardMarkup يظهر لمرة واحدة فقط للربط
        kb = [[KeyboardButton(f"🔗 اضغط هنا لاختيار {label}", 
                               request_chat=KeyboardButtonRequestChat(request_id=req_id, chat_is_channel=is_channel))]]
        
        await context.bot.send_message(
            chat_id=uid,
            text=f"يرجى الضغط على الزر في الأسفل لاختيار الـ {label} التي تريد ربطها:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)
        )

    elif query.data == 'acc':
        await query.edit_message_text(f"👤 <b>معلومات حسابك:</b>\n\nID: <code>{uid}</code>\nToken: <code>{u.get('secret_token')}</code>", 
                                      parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(u))

# --- معالجة الربط الناجح ---
async def handle_entity_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared_chat = update.message.chat_shared
    uid = update.effective_user.id
    entity_id = str(shared_chat.chat_id)
    random_id = secrets.token_hex(4).upper()
    
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO entities (user_id, entity_id, random_tag) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (entity_id) DO UPDATE SET user_id = EXCLUDED.user_id
        """, (uid, entity_id, random_id))
        conn.commit(); cur.close(); conn.close()
        
        u = await get_user_data(uid)
        await update.message.reply_text(
            f"✅ <b>تم ربط القناة بنجاح!</b>\n\n"
            f"الآن يمكنك الضغط على 🌐 <b>رابط الويب هوك</b> من القائمة الرئيسية.",
            parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(u)
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في الربط: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = await get_user_data(update.effective_user.id)
    # نرسل القائمة الداخلية فقط
    await update.message.reply_text("مرحباً بك في لوحة تحكم Mr.MOH الذكية 🤖", reply_markup=await get_main_menu(u))

@app.route('/')
def index(): return "Running..."

if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_entity_shared))
    application.run_polling()
