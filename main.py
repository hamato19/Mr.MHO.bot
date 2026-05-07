import os, secrets, asyncio, threading, logging, datetime, requests, time
from flask import Flask, request, jsonify
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- استيراد الملفات المساعدة (تأكد من وجودها في نفس المجلد) ---
import config
import keyboards  # تم التأكد من الربط
import services
import init_db
import security
import owner
import admin      # تم التأكد من الربط
import terms
import subscription

from database import get_db
from auth import activate_with_code

# الإعدادات الأساسية
BOT_TOKEN = config.BOT_TOKEN
ADMIN_ID = config.ADMIN_ID

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. تشغيل البداية ---
@security.rate_limit(seconds=1)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    services.initialize_user(uid)
    
    if int(uid) == ADMIN_ID:
        return await check_activation_logic(update, context)
        
    welcome_msg = "👋 مرحباً بك في نظام سمو الأرقام\nالرجاء اختيار اللغة:\n\nWelcome! Please choose your language:"
    # ربط كيبورد اللغة
    await update.effective_chat.send_message(welcome_msg, reply_markup=keyboards.get_language_keyboard())

# --- 2. معالج الأزرار الشامل ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    await query.answer()

    # فحص الحظر (للأعضاء فقط)
    if int(uid) != ADMIN_ID:
        is_blocked, _ = security.is_user_blocked(uid)
        if is_blocked: return await query.answer("🚫 حسابك مقيد حالياً.", show_alert=True)

    # --- أ. أزرار المستخدم العادي (مرتبطة بملف keyboards) ---
    if data.startswith('set_lang_'):
        lang = data.split('_')[2]
        context.user_data['selected_lang'] = lang
        await terms.send_terms(update, context, user_lang=lang)
        
    elif data == 'accept_terms' or data == 'home':
        await check_activation_logic(update, context)
        
    elif data == 'acc':
        user = services.get_user_data(uid)
        time_left = services.get_time_remaining(user['expiry_date'])
        txt = f"👤 <b>بيانات الحساب:</b>\n\n• الحالة: {'فعال ✅' if user['is_activated'] else 'متوقف ❌'}\n• المتبقي: {time_left}"
        # ربط زر العودة من ملف keyboards
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())
        
    elif data == 'renew_sub':
        user = services.get_user_data(uid)
        status_msg = (
            f"💳 <b>بيانات الاشتراك:</b>\n\n"
            f"📅 الانضمام: <code>{user.get('created_at', 'غير مسجل')}</code>\n"
            f"⏳ الانتهاء: <code>{user.get('expiry_date', 'غير محدد')}</code>\n\n"
            f"📥 <b>أدخل كود التفعيل (MHO-xxxx) الآن:</b>"
        )
        context.user_data['state'] = 'WAIT_CODE'
        await query.edit_message_text(status_msg, parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())

    # --- ب. أزرار الإدارة (مرتبطة بملف admin و keyboards) ---
    elif data.startswith(('admin_', 'gen_days_', 'manage_', 'adm_')):
        if int(uid) != ADMIN_ID: return
        
        if data == 'admin_panel': 
            await admin.show_admin_panel(update, context)
        elif data == 'admin_stats': 
            await admin.show_admin_stats(update)
        elif data == 'admin_users': 
            await admin.list_users(update)
        elif data in ['admin_generate_code', 'admin_gen_codes']: 
            await admin.show_generate_code_menu(update)
        elif data.startswith('manage_'):
            # استخراج الآيدي بشكل صحيح وتمريره لملف admin
            target_id = data.replace('manage_', '')
            await admin.manage_single_user(update, context, target_id)
        elif data.startswith('gen_days_'):
            days = int(data.split('_')[-1])
            await admin.process_generate_code(update, days)
        elif data.startswith('adm_'):
            p = data.split('_')
            if len(p) >= 3: 
                await admin.handle_admin_actions(update, context, p[1], p[2])

# --- 3. نظام الهوك (TradingView) ---
@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    raw_data = request.get_data(as_text=True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT u.user_id FROM users u JOIN entities e ON u.user_id = e.user_id 
                           WHERE u.secret_token=%s AND e.entity_id=%s AND u.is_activated=TRUE""", (token, target_id))
            if not cur.fetchone(): return jsonify({"error": "Unauthorized"}), 403
    
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": target_id, "text": raw_data})
    return jsonify({"status": "sent"}), 200

# --- 4. منطق تفعيل الأكواد والرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    uid, text = update.effective_user.id, update.message.text.strip().upper()

    # تفعيل الكود
    if text.startswith("MHO-") or context.user_data.get('state') == 'WAIT_CODE':
        success, days = await activate_with_code(uid, text)
        if success:
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ تم التفعيل بنجاح لمدة {days} يوم!")
            return await check_activation_logic(update, context)
        await update.message.reply_text("❌ الكود خاطئ أو مستخدم.")

# --- 5. التحقق من حالة الاشتراك (الربط مع ملف keyboards) ---
async def check_activation_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot_me = await context.bot.get_me()
    
    if int(uid) == ADMIN_ID:
        await owner.bypass_subscription(uid)
        msg = "🌟 <b>لوحة تحكم المالك</b>"
        # ربط قائمة المالك من ملف keyboards
        kb = await keyboards.get_main_menu(uid, bot_me.username)
    else:
        user = services.get_user_data(uid)
        if not services.is_user_active(user):
            msg = "🚫 <b>اشتراكك منتهي</b>"
            # ربط كيبورد التجديد من ملف keyboards
            kb = keyboards.get_renewal_keyboard()
        else:
            msg = "🏠 <b>القائمة الرئيسية</b>"
            # ربط قائمة المستخدم من ملف keyboards
            kb = await keyboards.get_main_menu(uid, bot_me.username)

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await update.effective_chat.send_message(msg, reply_markup=kb, parse_mode=ParseMode.HTML)

# --- 6. التشغيل النهائي ---
if __name__ == "__main__":
    init_db.initialize_database()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # تشغيل Flask في ثريد منفصل للهوك
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000), daemon=True).start()
    
    print("🚀 Bot Sumou is Online & Fully Linked!")
    application.run_polling(drop_pending_updates=True)
