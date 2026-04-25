import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import secrets
import threading
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode, Bot, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters

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

# --- لوحة التحكم بنظام Profithook ---
def main_menu(u):
    l = u['lang']
    has_chans = len(u['chans']) > 0
    
    # 1. أزرار الكيبورد السفلي (لطلب القناة)
    kb_request = [[KeyboardButton(
        text="➕ " + ("ربط قناة جديدة" if l=='ar' else "Link New Channel"),
        request_chat=KeyboardButtonRequestChat(
            request_id=1,
            chat_is_channel=True,
            user_administrator_rights={"can_post_messages": True}
        )
    )]]
    
    # 2. الأزرار الشفافة (Inline)
    inline_kb = [
        [InlineKeyboardButton("👤 " + ("حسابي" if l=='ar' else "Account"), callback_data='acc')]
    ]
    
    if has_chans:
        inline_kb.append([InlineKeyboardButton("🌐 " + ("رابط الويب هوك" if l=='ar' else "Webhook URL"), callback_data='url')])
    
    return ReplyKeyboardMarkup(kb_request, resize_keyboard=True), InlineKeyboardMarkup(inline_kb)

# --- معالجة استلام القناة المحددة ---
def handle_shared_chat(update: Update, context: CallbackContext):
    if update.message.chat_shared:
        chat_id = update.message.chat_shared.chat_id
        uid = update.effective_user.id
        
        # محاولة جلب معلومات القناة للتأكد من وجود البوت فيها
        try:
            chat_info = context.bot.get_chat(chat_id)
            chat_title = chat_info.title
            
            conn = get_db(); c = conn.cursor()
            c.execute("""
                INSERT INTO entities (user_id, entity_id, entity_name) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (entity_id) DO UPDATE SET user_id = %s, entity_name = %s
            """, (uid, str(chat_id), chat_title, uid, chat_title))
            conn.commit(); c.close(); conn.close()
            
            update.message.reply_text(f"✅ <b>تم الربط بنجاح!</b>\nالقناة: {chat_title}\nالمعرف: <code>{chat_id}</code>", 
                                    parse_mode='HTML', reply_markup=main_menu(get_user_full_data(uid))[1])
        except Exception as e:
            update.message.reply_text("⚠️ فشل الربط. تأكد أن البوت مشرف في القناة أولاً.")

# --- المعالجات المعتادة ---
def start(update, context):
    u = get_user_full_data(update.effective_user.id)
    reply_kb, inline_kb = main_menu(u)
    update.message.reply_text("👋 <b>MrMOH Smart System</b>\nاضغط على الزر بالأسفل لربط قناتك فوراً.", 
                            reply_markup=reply_kb, parse_mode='HTML')
    update.message.reply_text("قائمة التحكم:", reply_markup=inline_kb)

def handle_cb(update, context):
    q = update.callback_query
    u = get_user_full_data(q.from_user.id)
    q.answer()
    if q.data == 'url':
        q.edit_message_text(f"🌐 <b>رابط الويب هوك:</b>\n\n<code>{RENDER_URL}/webhook/{u['secret_token']}</code>", 
                          reply_markup=main_menu(u)[1], parse_mode='HTML')
    elif q.data == 'acc':
        names = ", ".join([c['entity_name'] for c in u['chans']]) if u['chans'] else "لا يوجد"
        q.edit_message_text(f"👤 <b>الحساب:</b> {u['user_id']}\n📡 <b>القنوات:</b> {names}", 
                          reply_markup=main_menu(u)[1])

# --- Flask Webhook ---
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

if __name__ == '__main__':
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_cb))
    # الهاندلر الجديد لالتقاط القناة المختارة
    dp.add_handler(MessageHandler(Filters.chat_shared, handle_shared_chat))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    updater.start_polling(drop_pending_updates=True)
    updater.idle()
