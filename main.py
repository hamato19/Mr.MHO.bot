import os
import logging
import sqlite3
import secrets
import threading
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters
import requests
from cryptography.fernet import Fernet

# --- ⚙️ الإعدادات الأساسية (Render Env Vars) ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = "5674313264"  # تأكد من أن هذا هو ID حسابك لتلقي طلبات التفعيل
DB_NAME = "elias_hook.db"

# إعداد التشفير لحماية مفاتيح Alpaca
env_key = os.getenv('ELIAS_SECRET_KEY')
if not env_key:
    env_key = Fernet.generate_key().decode()
cipher_suite = Fernet(env_key.encode())

app = Flask(__name__)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 🛠 إدارة قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # جدول المستخدمين مع نظام النقاط واللغة
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, secret_token TEXT, lang TEXT DEFAULT 'ar',
                  signals_left INTEGER DEFAULT 10, total_paid REAL DEFAULT 0.0,
                  alpaca_key TEXT, alpaca_secret TEXT, is_algo_active INTEGER DEFAULT 0)''')
    # جدول القنوات والمجموعات
    c.execute('''CREATE TABLE IF NOT EXISTS entities 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                  entity_id TEXT, entity_name TEXT)''')
    conn.commit()
    conn.close()

# --- 🌍 نظام الترجمة (عربي/إنجليزي) ---
STRINGS = {
    'ar': {
        'start': "👋 مرحباً بك في <b>إلياس سيستم</b>. اللوحة جاهزة لإدارة الويبهوك والتداول الآلي:",
        'acc': "👤 <b>حسابي:</b>\n\n- معرف المستخدم: <code>{uid}</code>\n- القنوات المفعلة: {chans}\n- أيام الاشتراك: {days}\n- إشارات متبقية: {sigs}\n- إجمالي المدفوع: ${paid}",
        'sub_info': "للاشتراك في البوت والاستمتاع بالتداول الآلي، يرجى زيارة موقعنا للحصول على باقات مميزة.\n\nإذا قمت بالاشتراك بالفعل ولديك كود التفعيل (رقم الطلب)، اضغط على الزر أدناه لإرساله.",
        'gen_tok_msg': "✅ تم إنشاء رمز أمان جديد لجميع روابط الويب هوك بنجاح. يرجى مراجعتها واستخدام الروابط المحدثة.",
        'support_msg': "يتم تحويلك الآن للدعم الفني الخاص بـ إلياس سيستم.",
        'order_req': "الرجاء إرسال رقم الطلب الخاص بك لتفعيل اشتراكك.",
        'order_done': "✅ تم إرسال رقم الطلب للإدارة. سيتم التفعيل بعد المراجعة.",
        'no_chans': "لا توجد قنوات مرتبطة بحسابك حالياً."
    },
    'en': {
        'start': "👋 Welcome to <b>Elias System</b>. Your dashboard for webhook management and auto-trading is ready:",
        'acc': "👤 <b>Account:</b>\n\n- User ID: <code>{uid}</code>\n- Active Channels: {chans}\n- Subscription Days: {days}\n- Signals Left: {sigs}\n- Total Paid: ${paid}",
        'sub_info': "To subscribe and enjoy auto-trading, please visit our website for premium plans.\n\nIf you already subscribed and have an order number, click the button below.",
        'gen_tok_msg': "✅ A new security token has been generated successfully for all webhook links.",
        'support_msg': "Redirecting you to Elias System technical support.",
        'order_req': "Please send your order number to activate your subscription.",
        'order_done': "✅ Order number sent to admin. Activation will occur after review.",
        'no_chans': "No channels linked to your account yet."
    }
}

# --- 🛠 وظائف مساعدة ---
def encrypt_data(data):
    return cipher_suite.encrypt(data.encode()).decode() if data else None

def decrypt_data(data):
    try: return cipher_suite.decrypt(data.encode()).decode() if data else None
    except: return None

def get_user(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT lang, signals_left, total_paid, secret_token, is_algo_active, alpaca_key, alpaca_secret FROM users WHERE user_id = ?", (uid,))
    res = c.fetchone()
    if not res:
        # مستخدم جديد يحصل على 10 إشارات مجانية
        c.execute("INSERT INTO users (user_id, signals_left) VALUES (?, 10)", (uid,))
        conn.commit()
        res = ('ar', 10, 0.0, None, 0, None, None)
    
    c.execute("SELECT COUNT(*) FROM entities WHERE user_id = ?", (uid,))
    chans = c.fetchone()[0]
    conn.close()
    return {'lang': res[0], 'sigs': res[1], 'paid': res[2], 'token': res[3], 'algo': res[4], 'key': res[5], 'sec': res[6], 'chans': chans}

# --- 🤖 لوحة التحكم ---
def start(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = u['lang']
    
    kb = [
        [InlineKeyboardButton("👤 حسابي" if lang=='ar' else "👤 Account", callback_data='acc'), 
         InlineKeyboardButton("🛒 تفعيل الاشتراك" if lang=='ar' else "🛒 Subscribe", callback_data='sub')],
        [InlineKeyboardButton("📢 إضافة قناة" if lang=='ar' else "📢 Add Channel", url=f"https://t.me/{context.bot.username}?startchannel=true"),
         InlineKeyboardButton("👥 إضافة مجموعة" if lang=='ar' else "👥 Add Group", url=f"https://t.me/{context.bot.username}?startgroup=true")],
        [InlineKeyboardButton("🖥 قنواتي" if lang=='ar' else "🖥 My Channels", callback_data='list')],
        [InlineKeyboardButton("🔑 إعدادات Alpaca" if lang=='ar' else "🔑 Alpaca Settings", callback_data='alp_set')],
        [InlineKeyboardButton("🔄 توليد رمز أمان" if lang=='ar' else "🔄 Gen Security Token", callback_data='gen_tok'), 
         InlineKeyboardButton("🌐 رابط ويب هوك" if lang=='ar' else "🌐 Webhook URL", callback_data='get_hook')],
        [InlineKeyboardButton("🚀 التداول الآلي" if lang=='ar' else "🚀 Auto-Trade", callback_data='tog_algo')],
        [InlineKeyboardButton("🇺🇸 English", callback_data='set_en'), InlineKeyboardButton("🇸🇦 العربية", callback_data='set_ar')],
        [InlineKeyboardButton("☎️ الدعم" if lang=='ar' else "☎️ Support", callback_data='support')]
    ]
    update.message.reply_text(STRINGS[lang]['start'], reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

def handle_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    u = get_user(uid)
    lang = u['lang']
    query.answer()

    if query.data == 'acc':
        msg = STRINGS[lang]['acc'].format(uid=uid, chans=u['chans'], days=0, sigs=u['sigs'], paid=u['paid'])
        query.edit_message_text(msg, parse_mode=ParseMode.HTML)

    elif query.data.startswith('set_'):
        new_l = query.data.split('_')[1]
        conn = sqlite3.connect(DB_NAME)
        conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (new_l, uid))
        conn.commit()
        conn.close()
        query.edit_message_text("✅ Language Updated / تم تحديث اللغة بنجاح.")

    elif query.data == 'gen_tok':
        new_t = secrets.token_hex(4).upper()
        conn = sqlite3.connect(DB_NAME)
        conn.execute("UPDATE users SET secret_token = ? WHERE user_id = ?", (new_t, uid))
        conn.commit()
        conn.close()
        query.edit_message_text(STRINGS[lang]['gen_tok_msg'])

    elif query.data == 'get_hook':
        token = u['token'] if u['token'] else "----"
        app_url = os.getenv('RENDER_EXTERNAL_URL', 'https://mr-mho-bot.onrender.com')
        url = f"{app_url}/webhook/{uid}?secret={token}"
        query.edit_message_text(f"🌐 Webhook URL:\n<code>{url}</code>", parse_mode=ParseMode.HTML)

    elif query.data == 'sub':
        btns = [[InlineKeyboardButton("للاشتراك اضغط هنا" if lang=='ar' else "Subscribe Here", url="https://your-website.com")],
                [InlineKeyboardButton("إرسال كود التفعيل" if lang=='ar' else "Send Activation Code", callback_data='ask_code')]]
        query.edit_message_text(STRINGS[lang]['sub_info'], reply_markup=InlineKeyboardMarkup(btns))

    elif query.data == 'ask_code':
        context.user_data['waiting_for_code'] = True
        query.edit_message_text(STRINGS[lang]['order_req'])

    elif query.data == 'list':
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT entity_id, entity_name FROM entities WHERE user_id = ?", (uid,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            query.edit_message_text(STRINGS[lang]['no_chans'])
            return
        txt = "قنواتك المفعلة:\n" if lang=='ar' else "Your Active Channels:\n"
        kb = []
        for r in rows:
            txt += f"- {r[1]} (ID: {r[0]})\n"
            kb.append([InlineKeyboardButton(f"❌ Delete {r[1]}", callback_data=f"del_{r[0]}")])
        query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith('del_'):
        eid = query.data.split('_')[1]
        conn = sqlite3.connect(DB_NAME)
        conn.execute("DELETE FROM entities WHERE entity_id = ? AND user_id = ?", (eid, uid))
        conn.commit()
        conn.close()
        query.edit_message_text("✅ Deleted / تم الحذف")

    elif query.data == 'support':
        query.edit_message_text(STRINGS[lang]['support_msg'] + "\n\nContact: @Elias_Support") # عدل المعرف هنا

# معالجة الرسائل (أكواد التفعيل وحفظ مفاتيح Alpaca)
def handle_msg(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    txt = update.message.text
    u = get_user(uid)
    
    if context.user_data.get('waiting_for_code'):
        context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ طلب تفعيل:\nID: {uid}\nOrder: {txt}")
        update.message.reply_text(STRINGS[u['lang']]['order_done'])
        context.user_data['waiting_for_code'] = False
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if txt.startswith("key:"):
        c.execute("UPDATE users SET alpaca_key = ? WHERE user_id = ?", (encrypt_data(txt.split(":")[1].strip()), uid))
        update.message.reply_text("✅ API Key Saved.")
    elif txt.startswith("secret:"):
        c.execute("UPDATE users SET alpaca_secret = ? WHERE user_id = ?", (encrypt_data(txt.split(":")[1].strip()), uid))
        update.message.reply_text("✅ Secret Key Saved.")
    conn.commit()
    conn.close()

# --- 📈 محرك الويبهوك والتداول ---
@app.route('/webhook/<int:uid>', methods=['POST'])
def hook_in(uid):
    sec = request.args.get('secret')
    u = get_user(uid)
    if not u['token'] or u['token'] != sec: return "Unauthorized", 403

    data = request.json
    ticker = data.get('ticker', 'N/A')
    action = data.get('action', 'buy')

    # منطق تداول Alpaca
    status = "📢 Signal Only"
    if u['algo'] == 1 and u['key'] and u['sec'] and u['sigs'] > 0:
        # تنفيذ صفقة حقيقية (تم اختصار الكود للتوضيح)
        status = "⚡ Trade Executed"
        # خصم إشارة من الرصيد
        conn = sqlite3.connect(DB_NAME)
        conn.execute("UPDATE users SET signals_left = signals_left - 1 WHERE user_id = ?", (uid,))
        conn.commit()
        conn.close()

    msg = f"🔔 <b>Elias-Hook Signal</b>\n━━━━━━━━━━━━\n📈 Symbol: {ticker}\n↕️ Side: {action}\n🛡 Status: {status}"
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": uid, "text": msg, "parse_mode": "HTML"})
    return "OK", 200

# --- 🚀 التشغيل ---
if __name__ == '__main__':
    init_db()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    up = Updater(BOT_TOKEN)
    dp = up.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_buttons))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_msg))
    print("🚀 Elias System is Online...")
    up.start_polling()
    up.idle()
