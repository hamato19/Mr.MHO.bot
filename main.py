import os
import logging
import secrets
import asyncio
import threading
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- الإعدادات ---
DB_URL = os.getenv('DB_URL', "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require")
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 8711658382 
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
main_loop = None
application = None 

# إعداد قاعدة البيانات
db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)
def get_db_conn(): return db_pool.getconn()
def release_db_conn(conn): db_pool.putconn(conn)

# --- القاموس المحدث ---
STRINGS = {
    'العربية': {
        'intro': "🤖 <b>مرحباً بك في Profit Hook!</b>\nنظام ربط TradingView بتلجرام عبر الويب هوك.",
        'welcome': "🏠 <b>القائمة الرئيسية:</b>",
        'buy_menu': "🛒 <b>تفعيل الاشتراك:</b>\nيمكنك الاشتراك عبر الرابط أو إرسال كود التفعيل للآدمن.",
        'acc_info': "👤 <b>بيانات حسابك:</b>\n🆔 معرفك: <code>{uid}</code>\n🔑 التوكن الحالي: <code>{token}</code>",
        'add_ch_msg': "📢 <b>أرسل الآن معرف القناة أو المجموعة (أرقام فقط):</b>\nمثال: <code>-100123456789</code>",
        'lang_select': "🌍 <b>اختر اللغة / Select Language:</b>",
        'no_ch': "❌ لا يوجد لديك قنوات مرتبطة حالياً.",
        'no_ch_gen': "⚠️ يجب إضافة قناة أولاً قبل توليد رمز أمان جديد.",
        'btns': {
            'acc': "👤 حسابي", 'buy': "🛒 تفعيل الاشتراك", 'my_ch': "📺 قنواتي",
            'add_ch': "📢 إضافة قناة", 'token': "🔄 توليد رمز أمان", 'wh': "🌐 رابط الويب هوك", 
            'how': "▶️ طريقة الاستخدام", 'lang': "🌍 اللغة / Language", 'support': "☎️ الدعم", 
            'tv': "📊 TradingView", 'back': "🏠 القائمة الرئيسية", 'del': "🗑️ حذف القناة"
        }
    },
    'English': {
        'intro': "🤖 <b>Welcome to Profit Hook!</b>",
        'welcome': "🏠 <b>Main Menu:</b>",
        'buy_menu': "🛒 <b>Activation:</b>",
        'acc_info': "👤 <b>Your Account:</b>\n🆔 ID: <code>{uid}</code>\n🔑 Token: <code>{token}</code>",
        'add_ch_msg': "📢 <b>Send Channel ID (Numbers only):</b>",
        'lang_select': "🌍 <b>Select Language:</b>",
        'no_ch': "❌ No linked channels.",
        'no_ch_gen': "⚠️ Add a channel first before generating a new token.",
        'btns': {
            'acc': "👤 My Account", 'buy': "🛒 Activation", 'my_ch': "📺 My Channels",
            'add_ch': "📢 Add Channel", 'token': "🔄 Refresh Token", 'wh': "🌐 Webhook Link", 
            'how': "▶️ How to use", 'lang': "🌍 Language", 'support': "☎️ Support", 
            'tv': "📊 TradingView", 'back': "🏠 Main Menu", 'del': "🗑️ Delete Channel"
        }
    }
}

# --- الدوال المساعدة ---
async def get_user_data(uid):
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
            if not user:
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token, language) VALUES (%s, %s, %s) RETURNING *", (str(uid), token, 'العربية'))
                conn.commit()
                user = cur.fetchone()
        return user
    finally: release_db_conn(conn)

async def get_main_menu(lang):
    B = STRINGS[lang]['btns']
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(B['acc'], callback_data='acc'), InlineKeyboardButton(B['buy'], callback_data='buy_menu')],
        [InlineKeyboardButton(B['add_ch'], callback_data='add_channel'), InlineKeyboardButton(B['my_ch'], callback_data='my_channels')],
        [InlineKeyboardButton(B['wh'], callback_data='url'), InlineKeyboardButton(B['token'], callback_data='gen_token')],
        [InlineKeyboardButton(B['lang'], callback_data='change_lang'), InlineKeyboardButton(B['how'], url="https://servernet.ct.ws")],
        [InlineKeyboardButton(B['tv'], web_app=WebAppInfo(url="https://www.tradingview.com"))],
        [InlineKeyboardButton(B['support'], url=f'tg://user?id={ADMIN_ID}')]
    ])

# --- الـ Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user_data(update.effective_user.id)
    lang = user['language']
    await update.message.reply_text(STRINGS[lang]['intro'], parse_mode=ParseMode.HTML)
    await update.message.reply_text(STRINGS[lang]['welcome'], reply_markup=await get_main_menu(lang), parse_mode=ParseMode.HTML)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    await query.answer()

    user = await get_user_data(uid)
    lang = user['language']
    T = STRINGS[lang]
    B = T['btns']

    if query.data == 'home':
        await query.edit_message_text(T['welcome'], reply_markup=await get_main_menu(lang), parse_mode=ParseMode.HTML)
    
    elif query.data == 'my_channels' or query.data == 'url':
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
                ents = cur.fetchall()
            
            if not ents:
                await query.edit_message_text(T['no_ch'], reply_markup=await get_main_menu(lang))
            else:
                txt = "📺 <b>قنواتك المرتبطة:</b>\n\n"
                keyboard = []
                for e in ents:
                    eid = e['entity_id']
                    wh = f"{DOMAIN}/webhook/{user['secret_token']}/{eid}"
                    txt += f"📍 ID: <code>{eid}</code>\n🔗 Link: <code>{wh}</code>\n"
                    txt += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                    # إضافة زر حذف لكل قناة
                    keyboard.append([InlineKeyboardButton(f"🗑️ حذف {eid}", callback_data=f"del_{eid}")])
                
                keyboard.append([InlineKeyboardButton(B['back'], callback_data='home')])
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        finally: release_db_conn(conn)

    elif query.data.startswith('del_'):
        target_eid = query.data.split('_')[1]
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (str(uid), str(target_eid)))
                conn.commit()
            await query.edit_message_text(f"✅ تم حذف القناة <code>{target_eid}</code> بنجاح.", parse_mode=ParseMode.HTML, reply_markup=await get_main_menu(lang))
        finally: release_db_conn(conn)

    # ... بقية حالات CallbackQuery (acc, buy_menu, etc.) تبقى كما هي في كودك الأصلي ...
    elif query.data == 'acc':
        txt = T['acc_info'].format(uid=uid, token=user['secret_token'])
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

    elif query.data == 'add_channel':
        context.user_data['state'] = 'wait_ch'
        await query.edit_message_text(T['add_ch_msg'], parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(B['back'], callback_data='home')]]))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get('state')
    user = await get_user_data(uid)
    lang = user['language']

    if state == 'wait_ch':
        raw_text = update.message.text.strip()
        # تحويل المدخل إلى رقم فقط (Int) لضمان نظافة قاعدة البيانات
        try:
            clean_id = str(int(raw_text)) # نتأكد أنه رقم ثم نحوله لنص للتخزين
            conn = get_db_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s)", (str(uid), clean_id))
                    conn.commit()
                context.user_data['state'] = None
                await update.message.reply_text(f"✅ تم ربط القناة {clean_id} بنجاح!", reply_markup=await get_main_menu(lang))
            except:
                await update.message.reply_text("❌ المعرف موجود مسبقاً أو هناك خطأ في الربط.")
            finally: release_db_conn(conn)
        except ValueError:
            await update.message.reply_text("⚠️ خطأ: يرجى إرسال أرقام فقط (معرف القناة)، مثال: -100123456789")

# --- Flask & Main (نفس الكود السابق مع استمرار تشغيل Webhook) ---
# ... (ضع بقية الدوال: telegram_webhook, trading_webhook, main) بنفس الترتيب ...

if __name__ == "__main__":
    asyncio.run(main())
