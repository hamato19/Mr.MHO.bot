import os, logging, secrets, psycopg2, asyncio, threading
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- 1. الإعدادات والقاموس ---
DB_URL = os.getenv('DB_URL', "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require")
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 8711658382
DOMAIN = os.getenv('DOMAIN', "https://moh-signalsbot.up.railway.app")

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
        'buy_title': "💎 <b>تفعيل الاشتراك المميز</b>\nأرسل رقم الطلب هنا للتفعيل.",
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
        'buy_title': "💎 <b>Premium Subscription</b>\nSend your Order ID for activation.",
        'alpaca_title': "🚀 <b>Alpaca Settings:</b>\nConfigure your trading keys.",
        'del_title': "❌ Select channel to remove:"
    }
}

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- 2. إدارة قاعدة البيانات ---
try:
    db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)
except Exception as e:
    logging.error(f"❌ DB Pool Error: {e}")

def get_db_conn(): return db_pool.getconn()
def release_db_conn(conn): db_pool.putconn(conn)

async def get_user_data(uid):
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            user = cur.fetchone()
            if not user:
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token, language) VALUES (%s, %s, %s) RETURNING *", (uid, token, 'العربية'))
                conn.commit()
                user = cur.fetchone()
            return user
    finally: release_db_conn(conn)

async def get_main_menu(lang):
    if lang == 'English':
        btns = [
            [InlineKeyboardButton("👤 Account", callback_data='acc'), InlineKeyboardButton("🛒 Activate", callback_data='buy')],
            [InlineKeyboardButton("📢 Add Channel", callback_data='add_channel'), InlineKeyboardButton("📺 My Channels", callback_data='my_channels')],
            [InlineKeyboardButton("❌ Remove Channel", callback_data='del_menu')],
            [InlineKeyboardButton("🌐 Webhooks", callback_data='url'), InlineKeyboardButton("🔄 New Token", callback_data='gen_token')],
            [InlineKeyboardButton("🌍 Language", callback_data='change_lang'), InlineKeyboardButton("🚀 Alpaca", callback_data='alpaca')],
            [InlineKeyboardButton("☎️ Support", url=f'tg://user?id={ADMIN_ID}')]
        ]
    else:
        btns = [
            [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')],
            [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📺 قنواتي", callback_data='my_channels')],
            [InlineKeyboardButton("❌ إزالة قناة", callback_data='del_menu')],
            [InlineKeyboardButton("🌐 روابط الويب هوك", callback_data='url'), InlineKeyboardButton("🔄 رمز أمان جديد", callback_data='gen_token')],
            [InlineKeyboardButton("🌍 تغيير اللغة", callback_data='change_lang'), InlineKeyboardButton("🚀 التداول الآلي", callback_data='alpaca')],
            [InlineKeyboardButton("☎️ الدعم", url=f'tg://user?id={ADMIN_ID}')]
        ]
    return InlineKeyboardMarkup(btns)

# --- 3. معالجة الأزرار (Callback Query) ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    await query.answer()
    
    user = await get_user_data(uid)
    lang = user.get('language', 'العربية') or 'العربية'
    T = STRINGS[lang]
    main_menu = await get_main_menu(lang)

    if query.data == 'home':
        await query.edit_message_text(T['main_menu'], parse_mode=ParseMode.HTML, reply_markup=main_menu)

    elif query.data == 'acc':
        await query.edit_message_text(T['acc_info'].format(uid=uid, token=user['secret_token']), parse_mode=ParseMode.HTML, reply_markup=main_menu)

    elif query.data == 'my_channels':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
                ents = cur.fetchall()
            if not ents:
                await query.edit_message_text(T['no_channels'], reply_markup=main_menu)
            else:
                txt = "📺 <b>قنواتك المضافة:</b>\n" if lang == 'العربية' else "📺 <b>Your Channels:</b>\n"
                for i, e in enumerate(ents, 1): txt += f"{i}- <code>{e['entity_id']}</code>\n"
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=main_menu)
        finally: release_db_conn(conn)

    elif query.data == 'del_menu':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
                ents = cur.fetchall()
            if not ents: await query.edit_message_text(T['no_channels'], reply_markup=main_menu)
            else:
                kb = [[InlineKeyboardButton(f"🗑 {e['entity_id']}", callback_data=f"remove_{e['entity_id']}")] for e in ents]
                kb.append([InlineKeyboardButton("🏠 عودة" if lang == 'العربية' else "🏠 Back", callback_data='home')])
                await query.edit_message_text(T['del_title'], reply_markup=InlineKeyboardMarkup(kb))
        finally: release_db_conn(conn)

    elif query.data.startswith('remove_'):
        eid = query.data.split('_')[1]
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (uid, eid))
                conn.commit()
            await query.edit_message_text(f"✅ Removed {eid}" if lang == 'English' else f"✅ تم حذف {eid}", reply_markup=main_menu)
        finally: release_db_conn(conn)

    elif query.data == 'url':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
                ents = cur.fetchall()
            if not ents: await query.edit_message_text(T['no_channels'], reply_markup=main_menu)
            else:
                txt = f"{T['webhooks_title']}\n\n"
                for e in ents:
                    url = f"{DOMAIN}/webhook/{user['secret_token']}/{e['entity_id']}"
                    txt += f"📢 <code>{e['entity_id']}</code>\n🔗 <code>{url}</code>\n\n"
                await context.bot.send_message(chat_id=uid, text=txt, parse_mode=ParseMode.HTML)
                await query.edit_message_text("✅ Sent to private chat" if lang == 'English' else "✅ تم الإرسال للخاص", reply_markup=main_menu)
        finally: release_db_conn(conn)

    elif query.data == 'change_lang':
        kb = [[InlineKeyboardButton("🇸🇦 العربية", callback_data='set_lang_ar')], [InlineKeyboardButton("🇺🇸 English", callback_data='set_lang_en')], [InlineKeyboardButton("🏠 عودة", callback_data='home')]]
        await query.edit_message_text("🌍 اختر اللغة / Choose Language", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith('set_lang_'):
        new_lang = "العربية" if query.data == 'set_lang_ar' else "English"
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET language = %s WHERE user_id = %s", (new_lang, uid))
                conn.commit()
            await query.edit_message_text(STRINGS[new_lang]['lang_success'], reply_markup=await get_main_menu(new_lang), parse_mode=ParseMode.HTML)
        finally: release_db_conn(conn)

    elif query.data == 'gen_token':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id FROM entities WHERE user_id = %s LIMIT 1", (uid,))
                if not cur.fetchone():
                    await query.edit_message_text(T['gen_token_err'], parse_mode=ParseMode.HTML, reply_markup=main_menu)
                else:
                    new_token = secrets.token_hex(8)
                    cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, uid))
                    conn.commit()
                    await query.edit_message_text(T['gen_token_ok'].format(token=new_token), parse_mode=ParseMode.HTML, reply_markup=main_menu)
        finally: release_db_conn(conn)

    elif query.data in ['add_channel', 'set_k', 'set_s', 'buy', 'alpaca']:
        if query.data == 'alpaca':
            alp_kb = [
                [InlineKeyboardButton("🔑 Key ID", callback_data='set_k'), InlineKeyboardButton("🔐 Secret Key", callback_data='set_s')],
                [InlineKeyboardButton("🏠 Back" if lang == 'English' else "🏠 عودة", callback_data='home')]
            ]
            await query.edit_message_text(T['alpaca_title'], parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(alp_kb))
        else:
            states = {'add_channel': 'wait_ch', 'set_k': 'wait_key', 'set_s': 'wait_sec', 'buy': 'wait_order'}
            prompts = {'add_channel': T['add_ch_prompt'], 'set_k': T['set_k_prompt'], 'set_s': T['set_s_prompt'], 'buy': T['ask_order']}
            context.user_data['state'] = states[query.data]
            await query.edit_message_text(prompts[query.data], parse_mode=ParseMode.HTML)

# --- 4. معالجة الرسائل النصية ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    state = context.user_data.get('state')
    user = await get_user_data(uid)
    lang = user['language'] or 'العربية'
    
    if state == 'wait_ch':
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (uid, text))
                conn.commit()
            await update.message.reply_text(f"✅ Added: {text}" if lang == 'English' else f"✅ تم إضافة: {text}", reply_markup=await get_main_menu(lang))
        except Exception as e:
            logging.error(f"Error adding entity: {e}")
            await update.message.reply_text("❌ Error adding channel")
        finally: release_db_conn(conn)
        context.user_data['state'] = None

    elif state in ['wait_key', 'wait_sec', 'wait_order']:
        col = "alpaca_key" if state == 'wait_key' else "alpaca_secret"
        if state == 'wait_order':
             # هنا يمكنك إضافة منطق التحقق من رقم الطلب لاحقاً
             await update.message.reply_text("✅ Order ID received. Support will verify it." if lang == 'English' else "✅ تم استلام رقم الطلب. سيقوم الدعم بالتحقق منه.", reply_markup=await get_main_menu(lang))
        else:
            conn = get_db_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE users SET {col} = %s WHERE user_id = %s", (text, uid))
                    conn.commit()
                await update.message.reply_text("✅ Saved!" if lang == 'English' else "✅ تم الحفظ!", reply_markup=await get_main_menu(lang))
            finally: release_db_conn(conn)
        context.user_data['state'] = None

# --- 5. تشغيل التطبيق ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_data(update.effective_user.id)
    await update.message.reply_text(STRINGS[user['language']]['main_menu'], parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(user['language']))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
