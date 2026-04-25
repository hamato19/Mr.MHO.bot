import os
import logging
import secrets
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat, Bot
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import threading

# --- الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL')
# تأكد من وضع رابط الويب هوك الخاص بك هنا أو في Variables
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- إدارة قاعدة البيانات ---
def get_db():
    return psycopg2.connect(DB_URL, sslmode='require')

async def get_user_full_data(uid):
    conn = get_db(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    user = c.fetchone()
    if not user:
        token = secrets.token_urlsafe(12).upper()
        c.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
        conn.commit()
        return await get_user_full_data(uid)
    c.execute("SELECT * FROM entities WHERE user_id = %s", (uid,))
    user['chans'] = c.fetchall() or []
    c.close(); conn.close()
    return user

# --- القوائم الذكية ---
async def get_menus(u):
    has_chans = len(u['chans']) > 0
    # زر طلب القناة - يفتح قائمة قنوات المستخدم مباشرة
    reply_kb = ReplyKeyboardMarkup([
        [KeyboardButton("➕ ربط قناة جديدة", request_chat=KeyboardButtonRequestChat(
            request_id=100, 
            chat_is_channel=True, 
            user_administrator_rights={"can_post_messages": True},
            bot_administrator_rights={"can_post_messages": True}
        ))]
    ], resize_keyboard=True)

    inline_kb = [[InlineKeyboardButton("👤 حسابي", callback_data='acc')]]
    if has_chans:
        inline_kb.append([InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='url')])
    
    return reply_kb, InlineKeyboardMarkup(inline_kb)

# --- معالجة الربط التلقائي (هنا السحر البرمجي) ---
async def handle_shared_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_shared:
        cid = update.message.chat_shared.chat_id
        uid = update.effective_user.id
        
        # محاولة جلب الاسم، وإذا تعذر نستخدم اسماً مؤقتاً لضمان عدم توقف الكود
        try:
            chat_obj = await context.bot.get_chat(cid)
            c_name = chat_obj.title
        except:
            c_name = f"قناة معرف: {cid}"

        conn = get_db(); c = conn.cursor()
        # الربط المباشر في قاعدة البيانات
        c.execute("""
            INSERT INTO entities (user_id, entity_id, entity_name) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (entity_id) DO UPDATE SET user_id = %s, entity_name = %s
        """, (uid, str(cid), c_name, uid, c_name))
        conn.commit(); c.close(); conn.close()
        
        # تحديث البيانات وإرسال المنيو الجديد فوراً
        u = await get_user_full_data(uid)
        _, inline_kb = await get_menus(u)
        
        await update.message.reply_text(
            f"✅ <b>تم الربط بنجاح!</b>\n\n📡 القناة: <b>{c_name}</b>\n🆔 المعرف: <code>{cid}</code>\n\nالآن تم تفعيل زر رابط الويب هوك بالأسفل 👇",
            reply_markup=inline_kb, parse_mode=ParseMode.HTML
        )

# --- الأوامر المعتادة ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = await get_user_full_data(update.effective_user.id)
    reply_kb, inline_kb = await get_menus(u)
    await update.message.reply_text(
        "👋 <b>مرحباً بك في MrMOH Smart</b>\n\nلربط قناتك واستلام الإشارات من TradingView، اضغط على الزر بالأسفل:", 
        reply_markup=reply_kb, parse_mode=ParseMode.HTML
    )
    await update.message.reply_text("لوحة التحكم الخاصة بك:", reply_markup=inline_kb)

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_user_full_data(query.from_user.id)
    await query.answer()
    
    if query.data == 'url':
        txt = f"🌐 <b>رابط الويب هوك الخاص بك:</b>\n\n<code>{RENDER_URL}/webhook/{u['secret_token']}</code>\n\n⚠️ ضعه في TradingView Alert URL."
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML)
    elif query.data == 'acc':
        names = "\n- ".join([c['entity_name'] for c in u['chans']]) if u['chans'] else "لا يوجد"
        txt = f"👤 <b>بيانات الحساب</b>\n\nID: <code>{u['user_id']}</code>\n\n📡 <b>القنوات المرتبطة:</b>\n- {names}"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML)

# --- نظام الويب هوك لاستقبال إشارات TradingView ---
@app.route('/webhook/<token>', methods=['POST'])
def webhook_api(token):
    # إنشاء بوت مؤقت لإرسال الرسالة بشكل متزامن
    temp_bot = Bot(token=BOT_TOKEN)
    conn = get_db(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id FROM users WHERE secret_token=%s", (token,))
    user = c.fetchone()
    if user:
        c.execute("SELECT entity_id FROM entities WHERE user_id=%s", (user['user_id'],))
        for row in c.fetchall():
            msg = request.json.get('message', '🚨 تنبيه جديد من النظام!')
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(temp_bot.send_message(row['entity_id'], msg, parse_mode=ParseMode.HTML))
                loop.close()
            except: pass
    c.close(); conn.close()
    return {"status": "ok"}

@app.route('/')
def home(): return "MOH Engine v20 is Live & Ready!"

if __name__ == '__main__':
    # تشغيل Flask في الخلفية
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000))), daemon=True).start()
    
    # بناء وتشغيل البوت
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_cb))
    application.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_shared_chat))
    
    print("Bot is starting...")
    application.run_polling()
