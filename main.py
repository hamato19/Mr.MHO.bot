import os
import secrets
import asyncio
import threading
import logging
import datetime
import requests
import time
from flask import Flask, request, jsonify
from telegram import Update, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# استيراد الملفات المساعدة
import config
import keyboards
import services
import init_db
import security
import owner
from database import get_db
from auth import activate_with_code
import admin  
import terms
import subscription

# الإعدادات الأساسية
BOT_TOKEN = config.BOT_TOKEN
ADMIN_ID = config.ADMIN_ID

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. معالجات الأوامر (Command Handlers) ---

@security.rate_limit(seconds=1)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    services.initialize_user(uid)

    if int(uid) == ADMIN_ID:
        return await check_activation_logic(update, context)

    welcome_msg = "👋 مرحباً بك في نظام سمو الأرقام\nالرجاء اختيار اللغة:\n\nWelcome! Please choose your language:"
    await update.effective_chat.send_message(
        welcome_msg, 
        reply_markup=keyboards.get_language_keyboard()
    )

# --- 2. معالج الأزرار (Callback Query Handler) ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    bot_me = await context.bot.get_me()
    await query.answer()

    if int(uid) != ADMIN_ID:
        is_blocked, _ = security.is_user_blocked(uid)
        if is_blocked:
            await query.answer("🚫 حسابك مقيد حالياً.", show_alert=True)
            return

    if data.startswith('set_lang_'):
        lang = data.split('_')[2]
        context.user_data['selected_lang'] = lang
        await terms.send_terms(update, context, user_lang=lang)
    elif data == 'accept_terms':
        await check_activation_logic(update, context)
    elif data == 'home':
        await check_activation_logic(update, context)

    elif data == 'acc':
        user = services.get_user_data(uid)
        time_left = services.get_time_remaining(user['expiry_date'])
        txt = f"👤 <b>بيانات الحساب:</b>\n\n• الحالة: {'فعال ✅' if user['is_activated'] else 'متوقف ❌'}\n• المتبقي: {time_left}"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())
    
    elif data == 'view_chs':
        ents = services.get_user_entities(uid)
        if not ents:
            return await query.edit_message_text("❌ لا توجد قنوات مرتبطة.", reply_markup=keyboards.get_back_to_home())
        await query.edit_message_text("📺 قنواتك المرتبطة:", reply_markup=await keyboards.get_entities_keyboard(ents))

    # --- قسم الإدارة (تم إصلاح زر التوليد هنا) ---
    elif data.startswith(('admin_', 'gen_days_', 'manage_', 'adm_')):
        if int(uid) != ADMIN_ID: return
        
        if data == 'admin_panel': 
            await admin.show_admin_panel(update, context)
        elif data == 'admin_stats': 
            await admin.show_admin_stats(update)
        elif data == 'admin_users': 
            await admin.list_users(update)
        # هنا الإصلاح: دمج الاحتمالين لزر التوليد لضمان العمل
        elif data in ['admin_generate_code', 'admin_gen_codes']:
            await admin.show_generate_code_menu(update)
        elif data.startswith('gen_days_'):
            days = int(data.split('_')[-1])
            await admin.process_generate_code(update, days)
        elif data.startswith('adm_'):
            parts = data.split('_')
            await admin.handle_admin_actions(update, parts[1], parts[2])

# --- 3. معالج الرسائل النصية ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    text = update.message.text
    user_fullname = update.effective_user.full_name

    if update.message.chat_shared:
        tid = str(update.message.chat_shared.chat_id)
        services.add_entity(uid, tid)
        await update.message.reply_text(f"✅ تم ربط القناة: {tid}")
        return await check_activation_logic(update, context)

    if not text: return
    
    if int(uid) != ADMIN_ID:
        is_blocked, mins = security.is_user_blocked(uid)
        if is_blocked:
            return await update.message.reply_text(f"🚫 حسابك مقيد. حاول بعد {mins} دقيقة.")
        
        if security.check_malicious_content(text):
            security.force_block_user(uid)
            await context.bot.send_message(ADMIN_ID, f"🛡️ محاولة تخريب من: {user_fullname} ({uid})\nالنص: {text}")
            return await update.message.reply_text("🚫 تم حظرك نهائياً لمحاولة التخريب.")

    if text.upper().startswith("MHO-") or context.user_data.get('state') == 'WAIT_CODE':
        success, days = await activate_with_code(uid, text.upper().strip())
        if success:
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ تم التفعيل بنجاح لمدة {days} يوم.")
            return await check_activation_logic(update, context)
        else:
            is_blocked, msg, att = security.log_failed_attempt(uid)
            if is_blocked:
                await context.bot.send_message(ADMIN_ID, f"🚨 حظر تخمين: {user_fullname}\nالكود: {text}")
                await update.message.reply_text(f"🚫 {msg}")
            else:
                await update.message.reply_text(f"❌ كود خاطئ. متبقي {3-att} محاولات.")

# --- 4. التحقق من الاشتراك ---

async def check_activation_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot_me = await context.bot.get_me()
    
    if int(uid) == ADMIN_ID:
        await owner.bypass_subscription(uid)
        msg = "🌟 <b>لوحة تحكم المالك | سمو الأرقام</b>"
    else:
        user = services.get_user_data(uid)
        if not services.is_user_active(user):
            return await subscription.send_renewal_request(update, context, user_data=user)
        msg = "🏠 <b>القائمة الرئيسية</b>"

    kb = await keyboards.get_main_menu(uid, bot_me.username)
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await update.effective_chat.send_message(msg, reply_markup=kb, parse_mode=ParseMode.HTML)

# --- 5. Flask Webhook (الرسائل الخام) ---

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    raw_data = request.get_data(as_text=True)
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.user_id FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token=%s AND e.entity_id=%s AND u.is_activated=TRUE
            """, (token, target_id))
            if not cur.fetchone(): return jsonify({"error": "Unauthorized"}), 403

    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                  json={"chat_id": target_id, "text": raw_data})
    return jsonify({"status": "sent"}), 200

# --- 6. التشغيل ---

if __name__ == "__main__":
    init_db.initialize_database()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000))), daemon=True).start()
    threading.Thread(target=services.keep_alive, daemon=True).start()
    
    print("🚀 Bot Sumou Al-Arqam is Online!")
    application.run_polling(drop_pending_updates=True)
