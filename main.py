import os
import logging
import secrets
import psycopg2
import asyncio
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import threading

# --- الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"
ADMIN_ID = 8711658382  # معرفك من Neon

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# إنشاء تطبيق التلجرام بشكل عالمي لاستخدامه داخل الويب هوك
application = ApplicationBuilder().token(BOT_TOKEN).build()

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

# --- اللوحة الرئيسية ---
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

WELCOME_MSG = (
    "👋 <b>أهلاً بك!</b>\n\n"
    "🆔 يرجى اختيار أحد الخيارات من اللوحة أدناه.\n\n"
    "⚠️ <b>تنبيه:</b> خدمة التداول الآلي لدينا تعمل فقط في القنوات، وليس في المجموعات.\n"
    "⚠️ عند إضافة البوت إلى قناة أو مجموعة، تأكد من منحه جميع الصلاحيات لضمان عمله بشكل صحيح."
)

# --- دالة استقبال الويب هوك من TradingView / Postman ---
@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        conn = get_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # التحقق من أن التوكن صحيح وجلب الـ user_id الخاص به
            cur.execute("SELECT user_id FROM users WHERE secret_token = %s", (token,))
            user = cur.fetchone()
            if not user:
                conn.close()
                return jsonify({"status": "error", "message": "Invalid token"}), 403
            
            uid = user['user_id']
            # جلب القنوات المربوطة بهذا المستخدم فقط لإرسال التنبيه لها
            cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
            entities = cur.fetchall()
        conn.close()

        if not entities:
            return jsonify({"status": "error", "message": "No entities linked to this account"}), 404

        # تنسيق رسالة التداول
        msg = (
            f"🔔 <b>تنبيه تداول جديد!</b>\n"
            f"📈 العملة: <code>{data.get('ticker', 'N/A')}</code>\n"
            f"⚡ النوع: <b>{data.get('action', 'N/A')}</b>\n"
            f"💰 السعر: <code>{data.get('price', 'N/A')}</code>\n"
            f"📝 الرسالة: {data.get('message', '')}"
        )

        # إرسال الرسالة لكل قناة مرتبطة بالمستخدم صاحب التوكن
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for entity in entities:
            try:
                loop.run_until_complete(application.bot.send_message(
                    chat_id=entity['entity_id'], 
                    text=msg, 
                    parse_mode=ParseMode.HTML
                ))
            except Exception as e:
                logging.error(f"Failed to send to {entity['entity_id']}: {e}")
        loop.close()

        return jsonify({"status": "success", "message": "Signal sent to your linked channels"}), 200

    except Exception as e:
        logging.error(f"Webhook Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

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
            await update.message.reply_text("⚠️ حدث خطأ في إشعار الإدارة، لكن طلبك مسجل.", reply_markup=await get_main_menu())
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

    elif query.data == 'back':
        await query.edit_message_text(WELCOME_MSG, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())

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
        await query.edit_message_text(f"🗑 تم الحذف بنجاح.", reply_markup=await get_main_menu())

    elif query.data == 'url':
