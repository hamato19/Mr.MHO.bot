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

# الإعدادات
BOT_TOKEN = config.BOT_TOKEN
DOMAIN = config.DOMAIN
ADMIN_ID = config.ADMIN_ID

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- المعالجات الأساسية ---

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

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    bot_me = await context.bot.get_me()
    await query.answer()

    # --- 1. إدارة اللغة والاشتراطات ---
    if data.startswith('set_lang_'):
        selected_lang = data.split('_')[2]
        context.user_data['selected_lang'] = selected_lang
        await terms.send_terms(update, context, user_lang=selected_lang)

    elif data == 'accept_terms':
        await check_activation_logic(update, context)

    elif data == 'decline_terms':
        try: await query.delete_message()
        except: pass
        await start(update, context)

    elif data == 'home':
        await check_activation_logic(update, context)
    
    # --- 2. إدارة الحساب والقنوات ---
    elif data == 'acc':
        user = services.get_user_data(uid)
        time_left = services.get_time_remaining(user['expiry_date'])
        txt = (f"👤 <b>بيانات الحساب:</b>\n\n"
               f"• الحالة: {'فعال ✅' if user['is_activated'] else 'متوقف ❌'}\n"
               f"• المتبقي: {time_left}\n"
               f"• الرمز: <code>{user['secret_token']}</code>")
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())

    elif data == 'add_ch':
        await context.bot.send_message(chat_id=uid, text="يرجى الضغط على الزر أدناه لاختيار القناة:", reply_markup=keyboards.get_channel_request_keyboard())

    elif data == 'view_chs':
        ents = services.get_user_entities(uid)
        if not ents: 
            return await query.edit_message_text("❌ لا توجد قنوات مرتبطة.", reply_markup=await keyboards.get_main_menu(uid, bot_me.username))
        
        import telegram
        kb = [[telegram.InlineKeyboardButton(f"🗑️ حذف {e['entity_id']}", callback_data=f"del_{e['entity_id']}")] for e in ents]
        kb.append([telegram.InlineKeyboardButton("🏠 عودة", callback_data='home')])
        await query.edit_message_text("📺 القنوات المرتبطة:", reply_markup=telegram.InlineKeyboardMarkup(kb))

    # --- إضافة دالة حذف القناة هنا ---
    elif data.startswith('del_'):
        entity_id = data.split('_')[1]
        try:
            services.delete_entity(uid, entity_id)
            await query.answer(f"🗑️ تم حذف القناة: {entity_id}", show_alert=True)
            # تحديث القائمة فوراً بعد الحذف
            return await check_activation_logic(update, context)
        except Exception as e:
            logging.error(f"Delete Entity Error: {e}")
            await query.answer("❌ فشل حذف القناة.")

    elif data == 'view_wh':
        user = services.get_user_data(uid)
        ents = services.get_user_entities(uid)
        txt = services.format_webhook_links(user['secret_token'], ents)
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())

    elif data == 'gen_token':
        new_token = secrets.token_hex(8)
        services.update_user_token(uid, new_token)
        await query.edit_message_text(f"✅ تم تحديث الرمز: <code>{new_token}</code>", parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())

    # --- 3. قسم لوحة التحكم والإدارة (للأدمن فقط) ---
    elif data.startswith(('admin_', 'gen_days_', 'manage_', 'adm_')):
        if int(uid) != ADMIN_ID:
            await query.answer("🚫 عذراً، هذه الصلاحية للمطور فقط.")
            return

        if data == 'admin_panel':
            await admin.show_admin_panel(update, context)
        elif data == 'admin_gen_codes' or data == 'admin_generate_code':
            await admin.show_generate_code_menu(update)
        elif data.startswith('gen_days_'):
            days = int(data.split('_')[-1])
            await admin.process_generate_code(update, days)
        elif data == 'admin_stats':
            await admin.show_admin_stats(update)
        elif data == 'admin_users':
            await admin.list_users(update)
        elif data.startswith('manage_user_'):
            user_id = data.replace('manage_user_', '')
            await admin.manage_single_user(update, user_id)
        elif data.startswith('adm_'):
            parts = data.split('_')
            action, target_id = parts[1], parts[2]
            if action == 'act': await admin.update_user_status(update, 'activate', target_id)
            elif action == 'deact': await admin.update_user_status(update, 'deactivate', target_id)
            elif action == 'del': await admin.update_user_status(update, 'delete', target_id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    text = update.message.text
    
    if update.message.chat_shared:
        tid = str(update.message.chat_shared.chat_id)
        services.add_entity(uid, tid)
        await update.message.reply_text(f"✅ تم ربط القناة: {tid}", reply_markup=ReplyKeyboardRemove())
        return await check_activation_logic(update, context)

    if text:
        text = security.sanitize_input(text).strip()
        
        if text.upper().startswith("MHO-"):
            success, days = await activate_with_code(uid, text.upper())
            if success:
                await update.message.reply_text(f"✅ تم تفعيل اشتراكك بنجاح لمدة {days} يوم!")
                return await check_activation_logic(update, context)
            else:
                await update.message.reply_text("❌ عذراً، هذا الكود غير صحيح أو مستخدم مسبقاً.")
                return

        if context.user_data.get('state') == 'WAIT_CODE':
            success, days = await activate_with_code(uid, text)
            if success:
                context.user_data['state'] = None
                await update.message.reply_text(f"✅ تم تفعيل الاشتراك لـ {days} يوم.")
                return await check_activation_logic(update, context)
            else: 
                await update.message.reply_text("❌ الكود غير صحيح.")

async def check_activation_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot_me = await context.bot.get_me()
    
    if int(uid) == ADMIN_ID:
        await owner.bypass_subscription(uid)
        msg = "🌟 <b>مرحباً بك يا مِستر MOH</b>\nتم تفعيل صلاحيات المالك."
    else:
        user = services.get_user_data(uid)
        if not services.is_user_active(user):
            return await subscription.send_renewal_request(update, context, user_data=user)
        msg = "🏠 <b>القائمة الرئيسية:</b>"

    if update.callback_query: 
        await update.callback_query.edit_message_text(msg, reply_markup=await keyboards.get_main_menu(uid, bot_me.username), parse_mode=ParseMode.HTML)
    else: 
        await update.effective_chat.send_message(msg, reply_markup=await keyboards.get_main_menu(uid, bot_me.username), parse_mode=ParseMode.HTML)

# --- Flask Server (Webhook) ---
@app.route('/')
def index(): return "🚀 Sumou System Online", 200

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    raw_data = request.get_data(as_text=True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT u.user_id FROM users u JOIN entities e ON u.user_id = e.user_id WHERE u.secret_token=%s AND e.entity_id=%s AND u.is_activated=TRUE", (token, target_id))
            if not cur.fetchone(): return jsonify({"error": "Unauthorized"}), 403
    
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": target_id, "text": raw_data})
    return jsonify({"status": "sent"}), 200

if __name__ == "__main__":
    init_db.initialize_database()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000))), daemon=True).start()
    threading.Thread(target=services.keep_alive, daemon=True).start()
    
    print("🚀 Bot is running...")
    application.run_polling(drop_pending_updates=True)
