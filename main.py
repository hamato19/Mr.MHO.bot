import os, secrets, asyncio, threading, logging
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonRequestChat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from database import get_db
from auth import check_user_access, activate_with_code

# الإعدادات
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
DOMAIN = os.getenv('DOMAIN')

app = Flask(__name__)
application = None
main_loop = None

# الأزرار والقوائم
async def get_main_menu(uid):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("📢 إضافة قناة", callback_data='add_ch')],
        [InlineKeyboardButton("🌐 الويب هوك", callback_data='view_wh'), InlineKeyboardButton("🔄 رمز جديد", callback_data='gen_token')],
        [InlineKeyboardButton("📺 قنواتي", callback_data='view_chs'), InlineKeyboardButton("☎️ الدعم", url=f"tg://user?id={ADMIN_ID}")],
    ]
    if uid == ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 توليد رمز (20 يوم)", callback_data='admin_gen_20')])
    return InlineKeyboardMarkup(kb)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    allowed, msg = await check_user_access(uid)
    
    if not allowed:
        context.user_data['state'] = 'WAIT_CODE'
        return await update.message.reply_text(f"👋 {msg}\n\nأرسل رمز التفعيل هنا 👇:", reply_markup=ReplyKeyboardRemove())

    await update.message.reply_text("🏠 <b>القائمة الرئيسية:</b>", reply_markup=await get_main_menu(uid), parse_mode=ParseMode.HTML)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    # معالجة التفعيل
    if context.user_data.get('state') == 'WAIT_CODE':
        success, days = await activate_with_code(uid, text)
        if success:
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ تم التفعيل بنجاح لمدة {days} يوماً!")
            return await start(update, context)
        return await update.message.reply_text("❌ الرمز غير صحيح. حاول مرة أخرى:")

    # ربط القنوات
    if context.user_data.get('state') == 'wait_ch' and update.message.chat_shared:
        ch_id = str(update.message.chat_shared.chat_id)
        with get_db() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), ch_id))
                    conn.commit()
                    await update.message.reply_text(f"✅ تم ربط القناة: {ch_id}")
                except: await update.message.reply_text("⚠️ القناة مرتبطة مسبقاً.")
        context.user_data['state'] = None
        return await start(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    data = query.data

    if data == 'add_ch':
        context.user_data['state'] = 'wait_ch'
        kb = [[KeyboardButton("📂 اختر القناة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
        await context.bot.send_message(chat_id=uid, text="📢 اختر القناة المراد ربطها:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    
    elif data == 'view_wh':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token FROM users WHERE user_id = %s", (str(uid),))
                token = cur.fetchone()['secret_token']
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        txt = "🌐 **روابط الويب هوك:**\n" + "\n".join([f"🔗 `{DOMAIN}/webhook/{token}/{e['entity_id']}`" for e in ents])
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(uid))

    elif data == 'admin_gen_20' and uid == ADMIN_ID:
        code = f"MOH-{secrets.token_hex(3).upper()}"
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO activation_codes (code, duration_days) VALUES (%s, 20)", (code,))
                conn.commit()
        await query.message.reply_text(f"🎟️ رمز 20 يوم جديد: `{code}`", parse_mode=ParseMode.HTML)

# --- Webhook (Flask) ---
@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    raw_data = request.get_data(as_text=True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users u JOIN entities e ON u.user_id = e.user_id WHERE u.secret_token=%s AND e.entity_id=%s AND u.is_activated=TRUE", (token, target_id))
            if not cur.fetchone(): return jsonify({"error": "unauthorized"}), 403
    
    asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id=target_id, text=f"<code>{raw_data}</code>", parse_mode=ParseMode.HTML), main_loop)
    return jsonify({"status": "ok"}), 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    main_loop = asyncio.new_event_loop()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("🚀 Mr.MOH Bot is LIVE!")
    application.run_polling()
