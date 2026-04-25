import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import secrets
import threading
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode, Bot
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters, ChatMemberHandler

# --- الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL')
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)

# --- قاعدة البيانات ---
def get_db():
    return psycopg2.connect(DB_URL, sslmode='require')

def get_user_full_data(uid):
    conn = get_db(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    user = c.fetchone()
    if not user:
        token = secrets.token_urlsafe(12).upper()
        c.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
        conn.commit()
        return get_user_full_data(uid)
    c.execute("SELECT * FROM entities WHERE user_id = %s", (uid,))
    user['chans'] = c.fetchall() or []
    c.close(); conn.close()
    return user

# --- لوحة التحكم الذكية ---
def smart_kb(u):
    l = u['lang']
    has_chans = len(u['chans']) > 0
    
    kb = [
        [InlineKeyboardButton("👤 " + ("حسابي" if l=='ar' else "Account"), callback_data='acc')],
        [InlineKeyboardButton("➕ " + ("إضافة قناة" if l=='ar' else "Add Channel"), url=f"https://t.me/{bot.get_me().username}?startchannel=true&admin=post_messages+edit_messages+delete_messages")],
        [InlineKeyboardButton("📈 " + ("تحليل الأسهم" if l=='ar' else "Analysis"), callback_data='analyze')]
    ]
    
    # لا يظهر زر الويب هوك إلا إذا وجد قناة مرتبطة
    if has_chans:
        kb.append([InlineKeyboardButton("🌐 " + ("رابط الويب هوك" if l=='ar' else "Webhook URL"), callback_data='url')])
    
    kb.append([InlineKeyboardButton("🇸🇦 / 🇺🇸 Language", callback_data='lang')])
    return InlineKeyboardMarkup(kb)

# --- معالجة إضافة البوت كمشرف (الربط التلقائي) ---
def track_chats(update: Update, context: CallbackContext):
    result = update.my_chat_member
    if result.new_chat_member.status == 'administrator':
        user_id = result.from_user.id
        chat = result.chat
        
        conn = get_db(); c = conn.cursor()
        c.execute("""
            INSERT INTO entities (user_id, entity_id, entity_name) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (entity_id) DO UPDATE SET entity_name = %s
        """, (user_id, str(chat.id), chat.title, chat.title))
        conn.commit(); c.close(); conn.close()
        
        # إشعار المستخدم بالنجاح
        context.bot.send_message(
            user_id, 
            f"✅ <b>تم ربط القناة بنجاح!</b>\nاسم القناة: {chat.title}\nالآن ظهر لك خيار 'رابط الويب هوك' في القائمة الرئيسية.",
            parse_mode='HTML'
        )

# --- المعالجات المعتادة ---
def start(update, context):
    u = get_user_full_data(update.effective_user.id)
    update.message.reply_text("👋 <b>MrMOH Smart System</b>\nأهلاً بك في نظام الأتمتة.", reply_markup=smart_kb(u), parse_mode='HTML')

def handle_cb(update, context):
    q = update.callback_query
    u = get_user_full_data(q.from_user.id)
    q.answer()

    if q.data == 'url':
        txt = f"🌐 <b>رابط الويب هوك الخاص بك:</b>\n\n<code>{RENDER_URL}/webhook/{u['secret_token']}</code>\n\n⚠️ استخدم هذا الرابط في TradingView لإرسال الإشارات."
        q.edit_message_text(txt, reply_markup=smart_kb(u), parse_mode='HTML')
    elif q.data == 'acc':
        chan_names = ", ".join([c['entity_name'] for c in u['chans']]) if u['chans'] else "لا يوجد"
        txt = f"👤 <b>بيانات الحساب</b>\n\nID: <code>{u['user_id']}</code>\nالقنوات المرتبطة: {chan_names}"
        q.edit_message_text(txt, reply_markup=smart_kb(u), parse_mode='HTML')

# --- Flask Webhook (لاستقبال إشارات TradingView) ---
@app.route('/webhook/<token>', methods=['POST'])
def webhook_api(token):
    conn = get_db(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id FROM users WHERE secret_token=%s", (token,))
    user = c.fetchone()
    if user:
        c.execute("SELECT entity_id FROM entities WHERE user_id=%s", (user['user_id'],))
        for row in c.fetchall():
            msg = request.json.get('message', '🚀 إشارة جديدة!')
            try: bot.send_message(row['entity_id'], msg, parse_mode='HTML')
            except: pass
    c.close(); conn.close()
    return {"status": "ok"}

@app.route('/')
def health(): return "System Online"

if __name__ == '__main__':
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_cb))
    # الهاندلر المسؤول عن التقاط إضافة البوت للقنوات
    dp.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    updater.start_polling(drop_pending_updates=True)
    updater.idle()
