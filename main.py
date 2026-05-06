import os, secrets, asyncio, threading, logging, datetime, requests, time
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonRequestChat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from psycopg2.extras import RealDictCursor

# استيراد الملفات المساعدة
from database import get_db
from auth import activate_with_code
import admin  
import terms
import i18n
import errors

# الإعدادات الأساسية
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

application = None

# --- الدوال المساعدة ---

def keep_alive():
    while True:
        try: requests.get(DOMAIN, timeout=10)
        except: pass
        time.sleep(20)

def get_time_remaining(expiry_date):
    if not expiry_date: return "غير مفعل 🔓"
    now = datetime.datetime.now()
    if now > expiry_date: return "منتهٍ 🛑"
    diff = expiry_date - now
    return f"{diff.days} يوم و {diff.seconds // 3600} ساعة"

async def get_main_menu(uid):
    try:
        bot_me = await application.bot.get_me()
        bot_username = bot_me.username
    except:
        bot_username = "bot"

    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("📢 ربط قناة", callback_data='add_ch')],
        [InlineKeyboardButton("🌐 روابط الويب هوك", callback_data='view_wh'), InlineKeyboardButton("🔄 تحديث الرمز", callback_data='gen_token')],
        [InlineKeyboardButton("📺 قنواتي المرتبطة", callback_data='view_chs')],
        [InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{bot_username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=f"tg://user?id={ADMIN_ID}")]
    ]
    if int(uid) == ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 لوحة التحكم (الأدمن)", callback_data='admin_panel')])
    return InlineKeyboardMarkup(kb)

# --- المعالجات المحدثة ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    
    uid = update.effective_user.id
    
    # 1. معالجة القنوات المشتركة (عند الضغط على زر اختيار قناة)
    if update.message.chat_shared:
        tid = str(update.message.chat_shared.chat_id)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (str(uid), tid))
                conn.commit()
        await update.message.reply_text(f"✅ تم ربط القناة بنجاح: {tid}", reply_markup=ReplyKeyboardRemove())
        return await check_activation_logic(update, context)

    # 2. معالجة النصوص (تفعيل الأكواد أو رسائل الإدارة)
    if update.message.text:
        text = update.message.text.strip()
        state = context.user_data.get('state')

        # منطق تفعيل الكود (المشتركين)
        if state == 'WAIT_CODE':
            success, days = await activate_with_code(uid, text)
            if success:
                context.user_data['state'] = None
                await update.message.reply_text(
                    f"✅ <b>تم التفعيل بنجاح!</b>\n⏳ مدة الاشتراك: {days} يوم.\n🚀 استمتع بكافة المميزات.",
                    parse_mode=ParseMode.HTML
                )
                return await check_activation_logic(update, context)
            else:
                await update.message.reply_text("❌ <b>الكود غير صحيح، منتهي، أو مستخدم مسبقاً.</b>", parse_mode=ParseMode.HTML)
        
        # منطق الإذاعة (الأدمن فقط)
        elif state == 'WAIT_BROADCAST_MSG' and uid == ADMIN_ID:
            await admin.exec_broadcast(update, context)

async def check_activation_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
    
    if not user or not user['is_activated']:
        context.user_data['state'] = 'WAIT_CODE'
        await update.effective_chat.send_message("⚠️ اشتراكك غير نشط، يرجى إرسال الكود:")
    else:
        await update.effective_chat.send_message("🌟 مرحباً بك في لوحة التحكم:", reply_markup=await get_main_menu(uid))

# --- باقي معالجات Callback و Flask (نفسها دون تغيير لضمان الاستقرار) ---
# [كود handle_callback و tv_webhook و start...]

if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000))), daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    application.run_polling(drop_pending_updates=True)
