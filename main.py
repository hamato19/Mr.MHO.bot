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
ADMIN_ID = 8711658382  # معرفك الشخصي من Neon

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

# --- اللوحة الرئيسية المحدثة (مطابقة للصورة) ---
async def get_main_menu():
    keyboard = [
        # الصف الأول
        [
            InlineKeyboardButton("👤 حسابي", callback_data='acc'),
            InlineKeyboardButton("🛒 تفعيل الاشتراك", callback_data='buy')
        ],
        # الصف الثاني
        [
            InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'),
            InlineKeyboardButton("📺 قنواتي", callback_data='my_channels')
        ],
        # الصف الثالث
        [
            InlineKeyboardButton("💬 إضافة مجموعة", callback_data='add_group')
        ],
        # الصف الرابع
        [
            InlineKeyboardButton("❌ إزالة قناة/مجموعة", callback_data='del_entity')
        ],
        # الصف الخامس
        [
            InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='url'),
            InlineKeyboardButton("🔄 توليد رمز أمان", callback_data='gen_token')
        ],
        # الصف السادس
        [
            InlineKeyboardButton("🌍 تغيير اللغة", callback_data='change_lang'),
            InlineKeyboardButton("▶️ طريقة الاستخدام", url='https://servernet.ct.ws')
        ],
        # الصف السابع
        [
            InlineKeyboardButton("🚀 التداول الآلي 🤖🚀", callback_data='alpaca')
        ],
        # الصف الثامن
        [
            InlineKeyboardButton("☎️ الدعم", url=f'tg://user?id={ADMIN_ID}')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- معالجة الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_order'):
        uid = update.effective_user.id
        order_no = update.message.text
        try:
            # إرسال تنبيه للأدمن
            await context.bot.send_message(
                chat_id=ADMIN_ID, 
                text=f"🚨 <b>طلب تفعيل جديد!</b>\n👤: <code>{uid}</code>\n🔢: <code>{order_no}</code>", 
                parse_mode=ParseMode.HTML
            )
            await update.message.reply_text(
                "✅ تم استلام رقم الطلب وإرساله للإدارة. سيتم تفعيل حسابك فور التأكد.", 
                reply_markup=await get_main_menu()
            )
        except:
            await update.message.reply_text("✅ تم الاستلام، جاري العودة للقائمة...", reply_markup=await get_main_menu())
        context.user_data['waiting_for_order'] = False

# --- معالجة الأزرار ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    await query.answer() # لزيادة الاستجابة
    
    u = await get_user_data(uid)

    if query.data == 'acc':
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM entities WHERE user_id = %s", (uid,))
        count = cur.fetchone()[0]
        conn.close()
        msg = (
            f"👤 <b>معلومات حسابك</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🆔: <code>{uid}</code>\n"
            f"📺: {count} كيان مربوط\n"
            f"⏳: {u.get('subscription_days',0)} يوم\n"
            f"📊: {u.get('remaining_signals',0)}\n"
            f"💰: ${u.get('total_paid',0.00):.2f}"
        )
        await query.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())

        elif query.data == 'buy':
        # أزرار قسم الاشتراك المحدثة
        keyboard = [
            [InlineKeyboardButton("🌐 للاشتراك اضغط هنا", url='https://servernet.ct.ws')],
            [InlineKeyboardButton("🔑 إرسال كود التفعيل", callback_data='submit_order')],
            [InlineKeyboardButton("📍 القائمة الرئيسية", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "<b>للاشتراك في البوت والاستمتاع بالتداول الآلي، يرجى زيارة موقعنا للحصول على باقات مميزة.</b>\n\n"
            "إذا قمت بالاشتراك بالفعل ولديك كود التفعيل (رقم الطلب)، اضغط على الزر أدناه لإرساله.",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    elif query.data == 'submit_order':
        # البدء في استقبال كود التفعيل من المستخدم
        await query.edit_message_text(
            "📝 <b>فضلاً، قم بكتابة كود التفعيل (رقم الطلب) الآن:</b>",
            parse_mode=ParseMode.HTML
        )
        context.user_data['waiting_for_order'] = True

    elif query.data == 'submit_order':
        await query.edit_message_text("📝 أرسل <b>رقم الطلب</b> الآن في رسالة نصية:", parse_mode=ParseMode.HTML)
        context.user_data['waiting_for_order'] = True

    elif query.data == 'gen_token':
        new_token = secrets.token_hex(8)
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, uid))
        conn.commit(); conn.close()
        await query.edit_message_text(f"✅ تم توليد رمز أمان جديد بنجاح!\nسيتم تحديث رابط الويب هوك تلقائياً.", reply_markup=await get_main_menu())

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
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (uid,))
        exists = cur.fetchone()
        conn.close()
        if exists:
            url = f"https://mr-mho-bot.onrender.com/webhook/{u['secret_token']}"
            await query.edit_message_text(f"🌐 <b>رابط الويب هوك:</b>\n<code>{url}</code>", parse_mode=ParseMode.HTML, reply_markup=await get_main_menu())
        else:
            await query.edit_message_text("⚠️ يجب ربط قناة أو مجموعة أولاً.", reply_markup=await get_main_menu())

    elif query.data == 'back':
        await query.edit_message_text("مرحباً بك في لوحة تحكم Mr.MOH 🤖", reply_markup=await get_main_menu())

    elif query.data in ['add_channel', 'add_group']:
        is_ch = (query.data == 'add_channel')
        req_id = 1 if is_ch else 2
        kb = [[KeyboardButton(f"🔗 اضغط هنا للربط", request_chat=KeyboardButtonRequestChat(request_id=req_id, chat_is_channel=is_ch))]]
        await context.bot.send_message(chat_id=uid, text="يرجى اختيار الكيان المراد ربطه:", 
                                       reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

# --- دوال الربط (Neon Integration) ---
async def handle_entity_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared = update.message.chat_shared if update.message.chat_shared else update.message.user_shared
    uid = update.effective_user.id
    eid = str(shared.chat_id)
    rtag = secrets.token_hex(4).upper()
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO entities (user_id, entity_id, random_tag) VALUES (%s, %s, %s) ON CONFLICT (entity_id) DO UPDATE SET user_id = EXCLUDED.user_id", (uid, eid, rtag))
        conn.commit(); conn.close()
        await update.message.reply_text(f"✅ تم الربط بنجاح!\nID: {eid}", reply_markup=await get_main_menu())
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في الربط: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً بك في لوحة تحكم Mr.MOH 🤖", reply_markup=await get_main_menu())

if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_entity_shared))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
