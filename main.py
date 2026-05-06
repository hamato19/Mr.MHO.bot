import os
import secrets
import asyncio
import threading
import logging
import datetime
import requests
import time
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
import subscription
import owner  # ملف استثناء المالك وتوليد الأكواد

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
        try: 
            requests.get(DOMAIN, timeout=10)
        except: 
            pass
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

# --- المعالجات الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s) ON CONFLICT DO NOTHING", (str(uid), secrets.token_hex(8)))
            conn.commit()

    if await owner.is_owner(uid):
        return await check_activation_logic(update, context)

    keyboard = [[InlineKeyboardButton("🇸🇦 العربية", callback_data='set_lang_ar'), InlineKeyboardButton("🇺🇸 English", callback_data='set_lang_en')]]
    welcome_msg = "👋 مرحباً بك في نظام سمو الأرقام\nالرجاء اختيار اللغة:\n\nWelcome! Please choose your language:"
    await update.effective_chat.send_message(welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    await query.answer()

    if data.startswith('set_lang_'):
        selected_lang = data.split('_')[2]
        context.user_data['selected_lang'] = selected_lang
        await terms.send_terms(update, context, user_lang=selected_lang)

    elif data == 'accept_terms':
        await check_activation_logic(update, context)

    elif data == 'decline_terms':
        try: await query.delete_message()
        except: pass
        await start(update, context)

    elif data == 'home':
        await check_activation_logic(update, context)
    
    elif data == 'acc':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token, expiry_date, is_activated FROM users WHERE user_id = %s", (str(uid),))
                user = cur.fetchone()
        txt = f"👤 <b>بيانات الحساب:</b>\n\n• الحالة: {'فعال ✅' if user['is_activated'] else 'متوقف ❌'}\n• المتبقي: {get_time_remaining(user['expiry_date'])}\n• الرمز: <code>{user['secret_token']}</code>"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    elif data == 'add_ch':
        kb = [[KeyboardButton("📢 اختر القناة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
        await context.bot.send_message(chat_id=uid, text="يرجى الضغط على الزر أدناه لاختيار القناة المراد ربطها:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

    elif data == 'view_chs':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents: return await query.edit_message_text("❌ لا توجد قنوات مرتبطة.", reply_markup=await get_main_menu(uid))
        kb = [[InlineKeyboardButton(f"🗑️ حذف {e['entity_id']}", callback_data=f"del_{e['entity_id']}")] for e in ents]
        kb.append([InlineKeyboardButton("🏠 عودة", callback_data='home')])
        await query.edit_message_text("📺 القنوات المرتبطة:", reply_markup=InlineKeyboardMarkup(kb))

    elif data == 'view_wh':
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT secret_token FROM users WHERE user_id = %s", (str(uid),))
                user_data = cur.fetchone()
                token = user_data['secret_token']
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
        if not ents: return await query.edit_message_text("⚠️ اربط قناة أولاً.", reply_markup=await get_main_menu(uid))
        txt = "🌐 <b>روابط الويب هوك:</b>\n\n"
        for e in ents: txt += f"• <code>{DOMAIN}/webhook/{token}/{e['entity_id']}</code>\n"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    elif data == 'gen_token':
        new_token = secrets.token_hex(8)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
                conn.commit()
        await query.edit_message_text(f"✅ تم تحديث الرمز: <code>{new_token}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]]))

    elif data == 'admin_panel' and int(uid) == ADMIN_ID:
        await admin.show_admin_panel(update, context)

    elif data.startswith(('admin_', 'gen_days_', 'manage_', 'adm_')):
        if int(uid) == ADMIN_ID:
            if data == 'admin_users': await admin.list_users(update)
        elif data.startswith(('admin_', 'gen_days_', 'manage_', 'adm_')):
        if int(uid) == ADMIN_ID:
            if data == 'admin_users': 
                await admin.list_users(update)
            elif data == 'admin_stats': 
                await admin.show_admin_stats(update)
            elif data.startswith('gen_days_'): 
                # هذا هو الجزء المسؤول عن توليد الأكواد
                days = int(data.split('_')[2])
                await owner.process_generate_code(update, days)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    
    if update.message.chat_shared:
        tid = str(update.message.chat_shared.chat_id)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (str(uid), tid))
                conn.commit()
        await update.message.reply_text(f"✅ تم ربط القناة: {tid}", reply_markup=ReplyKeyboardRemove())
        return await check_activation_logic(update, context)

    if update.message.text:
        text = update.message.text.strip()
        state = context.user_data.get('state')
        if state == 'WAIT_CODE':
            success, days = await activate_with_code(uid, text)
            if success:
                context.user_data['state'] = None
                await update.message.reply_text(f"✅ تم التفعيل لـ {days} يوم.")
                return await check_activation_logic(update, context)
            else: await update.message.reply_text("❌ كود خاطئ.")

async def check_activation_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if await owner.is_owner(uid):
        await owner.bypass_subscription(uid)
        msg_owner = "🌟 <b>مرحباً بك يا مِستر MOH</b>\nتم تفعيل صلاحيات المالك."
        if update.callback_query: await update.callback_query.edit_message_text(msg_owner, reply_markup=await get_main_menu(uid), parse_mode=ParseMode.HTML)
        else: await update.effective_chat.send_message(msg_owner, reply_markup=await get_main_menu(uid), parse_mode=ParseMode.HTML)
        return

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT is_activated, expiry_date FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
    
    now = datetime.datetime.now()
    if not user or not user['is_activated'] or (user['expiry_date'] and now > user['expiry_date']):
        await subscription.send_renewal_request(update, context, user_data=user)
    else:
        text = "🏠 <b>القائمة الرئيسية:</b>"
        if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=await get_main_menu(uid), parse_mode=ParseMode.HTML)
        else: await update.effective_chat.send_message(text, reply_markup=await get_main_menu(uid), parse_mode=ParseMode.HTML)

# --- Flask Server (Webhook) ---
@app.route('/')
def index(): return "🚀 Sumou System Online", 200

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    raw_data = request.get_data(as_text=True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.user_id FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token=%s AND e.entity_id=%s AND u.is_activated=TRUE
            """, (token, target_id))
            if not cur.fetchone(): return jsonify({"error": "Unauthorized"}), 403
    
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": target_id, 
        "text": raw_data, 
        "parse_mode": None 
    })
    return jsonify({"status": "sent"}), 200

if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000))), daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    application.run_polling(drop_pending_updates=True)
