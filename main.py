import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import secrets
import threading
from flask import Flask, request, render_template_string
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode, Bot, WebAppInfo
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters, ChatMemberHandler

# --- ⚙️ الإعدادات الأساسية ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL')
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', 'https://your-app.onrender.com')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)

# --- 🛠 إدارة قاعدة البيانات ---
def get_db_connection():
    return psycopg2.connect(DB_URL, sslmode='require')

def init_db():
    conn = get_db_connection(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, secret_token TEXT, lang TEXT DEFAULT 'ar',
                  signals_left INTEGER DEFAULT 10, total_paid REAL DEFAULT 0.0,
                  expiry_days INTEGER DEFAULT 0, is_active BOOLEAN DEFAULT TRUE,
                  state TEXT DEFAULT 'IDLE')''')
    c.execute('''CREATE TABLE IF NOT EXISTS entities 
                 (id SERIAL PRIMARY KEY, user_id BIGINT, 
                  entity_id TEXT UNIQUE, entity_name TEXT, entity_type TEXT)''')
    conn.commit(); c.close(); conn.close()

def get_user_data(uid):
    conn = get_db_connection(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    if not res:
        token = secrets.token_urlsafe(16).upper()
        c.execute("INSERT INTO users (user_id, secret_token, signals_left) VALUES (%s, %s, 10)", (uid, token))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
    c.execute("SELECT * FROM entities WHERE user_id = %s", (uid,))
    res['chans'] = c.fetchall()
    c.close(); conn.close()
    return res

# --- ⌨️ لوحات التحكم المحدثة ---
def get_main_keyboard():
    # رابط التطبيق المصغر لعرض الشارت
    chart_web_app = WebAppInfo(url=f"{RENDER_URL}/chart")
    
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'),
         InlineKeyboardButton("📊 عرض الشارات", web_app=chart_web_app)], # ميزة التطبيق المصغر
        [InlineKeyboardButton("➕ إضافة قناة", url=f"https://t.me/{bot.get_me().username}?startchannel=true"),
         InlineKeyboardButton("🗑 حذف قناة", callback_data='list_to_del')],
        [InlineKeyboardButton("🔐 تجديد التوكن", callback_data='gen_token'),
         InlineKeyboardButton("🎫 تفعيل الاشتراك", callback_data='sub_activate')],
        [InlineKeyboardButton("🌐 الويب هوك", callback_data='get_hook')]
    ]
    return InlineKeyboardMarkup(kb)

# --- 🤖 معالجات البوت ---

def start(update: Update, context: CallbackContext):
    u = get_user_data(update.effective_user.id)
    update.message.reply_text(
        f"👋 مرحباً بك في <b>MOH Engine</b>\nالنظام جاهز للعمل. يمكنك الآن عرض الشارات مباشرة عبر التطبيق المصغر بالأسفل.", 
        reply_markup=get_main_keyboard(), 
        parse_mode=ParseMode.HTML
    )

def handle_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    u = get_user_data(uid)
    query.answer()

    if query.data == 'acc':
        txt = (f"👤 <b>حسابي</b>\n\n"
               f"- معرف المستخدم: <code>{uid}</code>\n"
               f"- القنوات المفعلة: {len(u['chans'])}\n"
               f"- أيام الاشتراك: {u['expiry_days']}\n"
               f"- إشارات متبقية: {u['signals_left']}\n"
               f"- إجمالي المدفوع: ${u['total_paid']:.2f}")
        query.edit_message_text(txt, reply_markup=get_main_keyboard(), parse_mode=ParseMode.HTML)

    elif query.data == 'gen_token':
        new_token = secrets.token_urlsafe(16).upper()
        conn = get_db_connection(); c = conn.cursor()
        c.execute("UPDATE users SET secret_token=%s WHERE user_id=%s", (new_token, uid))
        conn.commit(); c.close(); conn.close()
        hook_url = f"{RENDER_URL}/webhook/{new_token}"
        bot.send_message(chat_id=uid, text=f"🔐 <b>تم تجديد التوكن بنجاح!</b>\n\nرابطك الجديد:\n<code>{hook_url}</code>", parse_mode=ParseMode.HTML)

    elif query.data == 'list_to_del':
        if not u['chans']:
            query.edit_message_text("⚠️ لا توجد قنوات مضافة حالياً.", reply_markup=get_main_keyboard())
        else:
            buttons = [[InlineKeyboardButton(f"❌ {c['entity_name']}", callback_data=f"del_{c['id']}")] for c in u['chans']]
            buttons.append([InlineKeyboardButton("🔙 عودة", callback_data='acc')])
            query.edit_message_text("اختر القناة التي تريد حذفها:", reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith('del_'):
        cid = query.data.split('_')[1]
        conn = get_db_connection(); c = conn.cursor()
        c.execute("DELETE FROM entities WHERE id=%s AND user_id=%s", (cid, uid))
        conn.commit(); c.close(); conn.close()
        query.edit_message_text("✅ تم حذف القناة بنجاح.", reply_markup=get_main_keyboard())

    elif query.data == 'get_hook':
        hook_url = f"{RENDER_URL}/webhook/{u['secret_token']}"
        query.edit_message_text(f"🌐 <b>رابط الويب هوك الخاص بك:</b>\n<code>{hook_url}</code>\n\n⚠️ لا تشارك هذا الرابط مع أحد.", reply_markup=get_main_keyboard(), parse_mode=ParseMode.HTML)

def track_new_channel(update: Update, context: CallbackContext):
    if update.my_chat_member and update.my_chat_member.new_chat_member.status in ['administrator']:
        chat = update.my_chat_member.chat
        user_id = update.my_chat_member.from_user.id
        
        conn = get_db_connection(); c = conn.cursor()
        c.execute("INSERT INTO entities (user_id, entity_id, entity_name, entity_type) VALUES (%s, %s, %s, %s) ON CONFLICT (entity_id) DO NOTHING", 
                  (user_id, str(chat.id), chat.title, chat.type))
        conn.commit(); c.close(); conn.close()
        
        u = get_user_data(user_id)
        hook_url = f"{RENDER_URL}/webhook/{u['secret_token']}"
        
        try:
            bot.send_message(
                chat_id=user_id,
                text=(f"🔗 <b>تم إضافة قناتك بنجاح!</b>\n\n"
                      f"اسم القناة: {chat.title}\n"
                      f"رابط الويب هوك الخاص بك:\n<code>{hook_url}</code>\n\n"
                      f"💡 <i>استخدم تطبيق المصغر في البوت لمتابعة الشارات.</i>"),
                parse_mode=ParseMode.HTML
            )
        except: pass

# --- 🕸 Flask Routes (Webhook + Chart WebApp) ---

@app.route('/chart')
def chart_page():
    # واجهة HTML بسيطة مدمجة لعرض شارت TradingView الاحترافي داخل التليجرام
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Live Charts</title>
        <style>
            body { margin: 0; padding: 0; background-color: #131722; height: 100vh; overflow: hidden; }
            .tradingview-widget-container { height: 100vh; width: 100%; }
        </style>
    </head>
    <body>
        <div class="tradingview-widget-container">
            <div id="tradingview_chart"></div>
            <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
            <script type="text/javascript">
            new TradingView.widget({
                "autosize": true,
                "symbol": "BINANCE:BTCUSDT",
                "interval": "D",
                "timezone": "Etc/UTC",
                "theme": "dark",
                "style": "1",
                "locale": "ar",
                "toolbar_bg": "#f1f3f6",
                "enable_publishing": false,
                "allow_symbol_change": true,
                "container_id": "tradingview_chart"
            });
            </script>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_content)

@app.route('/webhook/<token>', methods=['POST'])
def webhook_receiver(token):
    data = request.json or {}
    conn = get_db_connection(); c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id, signals_left FROM users WHERE secret_token = %s", (token,))
    user = c.fetchone()
    
    if user and user['signals_left'] > 0:
        c.execute("SELECT entity_id FROM entities WHERE user_id = %s", (user['user_id'],))
        msg = data.get('message', '🚀 إشارة جديدة مكتشفة!')
        
        c.execute("UPDATE users SET signals_left = signals_left - 1 WHERE user_id = %s", (user['user_id'],))
        conn.commit()
        
        for chan in c.fetchall():
            try: bot.send_message(chat_id=chan['entity_id'], text=msg, parse_mode=ParseMode.HTML)
            except: pass
            
    c.close(); conn.close()
    return {"status": "ok"}, 200

# --- 🚀 التشغيل ---
if __name__ == '__main__':
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_callbacks))
    dp.add_handler(ChatMemberHandler(track_new_channel, ChatMemberHandler.MY_CHAT_MEMBER))

    # تشغيل Flask وتلقي طلبات الويب هوك والتطبيق المصغر
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    
    updater.start_polling(drop_pending_updates=True)
    updater.idle()
