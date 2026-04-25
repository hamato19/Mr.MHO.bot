import os
import logging
import secrets
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import threading

# --- الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"
ADMIN_ID = 8711658382  # معرفك من Neon

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def get_db():
    return psycopg2.connect(DB_URL)

async def get_user_data(uid):
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
            user = cur.fetchone()
            if not user:
                token = secrets.token_hex(8)
                cur.execute("INSERT INTO users (user_id, secret_token) VALUES (%s, %s)", (uid, token))
                conn.commit()
                user = {"user_id": uid, "secret_token": token}
        conn.close()
        return user
    except Exception as e:
        logging.error(f"DB Error: {e}")
        return None

# --- اللوحة الرئيسية (تصميم الصورة 1) ---
async def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📺 قنواتي", callback_data='my_channels')],
        [InlineKeyboardButton("💬 إضافة مجموعة", callback_data='add_group')],
        [InlineKeyboardButton("❌ إزالة قناة/مجموعة", callback_data='del_entity')],
        [InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='url'), InlineKeyboardButton("🔄 توليد رمز أمان", callback_data='gen_token')],
        [InlineKeyboardButton("🌍 تغيير اللغة", callback_data='change_lang'), InlineKeyboardButton("▶️ طريقة الاستخدام", url='https://servernet.ct.ws')],
        [InlineKeyboardButton("🚀 التداول الآلي 🤖🚀", callback_data='alpaca')],
        [InlineKeyboardButton("☎️ الدعم", url=f'tg://user?id={ADMIN_ID}')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- معالجة الرسائل واستلام كود التفعيل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_order'):
        uid = update.effective_user.id
        order_no = update.message.text
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID, 
                text=f"🚨 <b>طلب تفعيل جديد!</b>\n👤 الشخص: <code>{uid}</code>\n🔑 الكود: <code>{order_no}</code>", 
                parse_mode=ParseMode.HTML
            )
            await update.message.reply_text("✅ تم استلام رقم الطلب وإرساله للإدارة. سيتم تفعيل حسابك فور التأكد.", reply_markup=await get_main_menu())
        except:
            await update.message.reply_text("⚠️ حدث خطأ في التواصل مع الإدارة، لكن تم تسجيل طلبك.", reply_markup=await get_main_menu())
        context.user_data['waiting_for_order'] = False

# --- معالجة الأزرار ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    await query.answer()
    u = await get_user_data(uid)

    if query.data == 'acc':
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (uid,))
        channels_count = cur.fetchone()[0]
        cur.close(); conn.close()
        msg = f"👤 <b>معلومات حسابك</b>\n━━━━━━━━━━━━━━━\n🆔: <code>{uid}</code>\n📺: {channels_count} كيان مربوط\n⏳: {u.get('subscription_days',0)} يوم\n📊: {u.get('remaining_signals',0)}"
        await query.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())

    elif query.data == 'buy':
        # تصميم زر تفعيل الاشتراك المحدث
        keyboard = [
            [InlineKeyboardButton("🌐 للاشتراك اضغط هنا", url='https://servernet.ct.ws')],
            [InlineKeyboardButton("🔑 إرسال كود التفعيل", callback_data='submit_order')],
            [InlineKeyboardButton("📍 القائمة الرئيسية", callback_data='back')]
        ]
        await query.edit_message_text(
            "<b>للاشتراك في البوت والاستمتاع بالتداول الآلي، يرجى زيارة موقعنا للحصول على باقات مميزة.</b>\n\n"
            "إذا قمت بالاشتراك بالفعل ولديك كود التفعيل (رقم الطلب)، اضغط على الزر أدناه لإرساله.",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == 'submit_order':
        await query.edit_message_text("📝 <b>فضلاً، قم بكتابة كود التفعيل (رقم الطلب) الآن في رسالة:</b>", parse_mode=ParseMode.HTML)
        context.user_data['waiting_for_order'] = True

    elif query.data == 'del_entity':
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
        entities = cur.fetchall()
        conn.close()
        if not entities:
            await query.edit_message_text("❌ لا توجد قنوات مسجلة لحذفها.", reply_markup=await get_main_menu())
            return
        kb = [[InlineKeyboardButton(f"🗑 حذف {e[0]}", callback_data=f"remove_{e[0]}")] for e in entities]
        kb.append([InlineKeyboardButton("🔙 إلغاء", callback_data='back')])
        await query.edit_message_text("❌ <b>اختر القناة/المجموعة المراد حذفها:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif query.data.startswith('remove_'):
        eid = query.data.replace('remove_', '')
        conn = get_db(); cur = conn.cursor()
        cur.execute("DELETE FROM entities WHERE entity_id = %s AND user_id = %s", (eid, uid))
        conn.commit(); conn.close()
        await query.edit_message_text(f"🗑 تم حذف الكيان بنجاح من قاعدة البيانات.", reply_markup=await get_main_menu())

    elif query.data == 'url':
        url = f"https://mr-mho-bot.onrender.com/webhook/{u['secret_token']}"
        await query.edit_message_text(f"🌐 <b>رابط الويب هوك الخاص بك:</b>\n<code>{url}</code>", parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())

    elif query.data == 'gen_token':
        new_token = secrets.token_hex(8)
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, uid))
        conn.commit(); conn.close()
        await query.edit_message_text("✅ تم توليد رمز أمان جديد وتحديث الويب هوك.", reply_markup=await get_main_menu())

    elif query.data == 'back':
        await query.edit_message_text("مرحباً بك في لوحة تحكم Mr.MOH 🤖", reply_markup=await get_main_menu())

# --- دوال الربط (Neon Integration) ---
async def handle_entity_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared = update.message.chat_shared if update.message.chat_shared else update.message.user_shared
    uid = update.effective_user.id
    eid = str(shared.chat_id)
    rtag = secrets.token_hex(4).upper()
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO entities (user_id, entity_id, random_tag) VALUES (%s, %s, %s) ON CONFLICT (entity_id) DO UPDATE SET user_id = EXCLUDED.user_id", (uid, eid, rtag))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ تم ربط الكيان {eid} بنجاح!", reply_markup=await get_main_menu())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("    "👋 <b>أهلاً بك!</b>\n\n"
        "🆔 يرجى اختيار أحد الخيارات من اللوحة أدناه.\n\n"
        "⚠️ <b>تنبيه:</b> خدمة التداول الآلي لدينا تعمل فقط في القنوات، وليس في المجموعات.\n"
        "⚠️ عند إضافة البوت إلى قناة أو مجموعة، تأكد من منحه جميع الصلاحيات لضمان عمله بشكل", reply_markup=await get_main_menu())

if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_entity_shared))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
