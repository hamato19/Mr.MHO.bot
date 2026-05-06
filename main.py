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

    # فحص الحظر قبل معالجة أي ضغطة زر
    is_blocked, _ = security.is_user_blocked(uid)
    if is_blocked:
        await query.answer("🚫 حسابك مقيد حالياً.", show_alert=True)
        return

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

    elif data.startswith('del_'):
        entity_id = data.split('_')[1]
        services.delete_entity(uid, entity_id)
        await query.answer(f"🗑️ تم حذف القناة: {entity_id}", show_alert=True)
        await check_activation_logic(update, context)

    elif data == 'view_wh':
        user = services.get_user_data(uid)
        ents = services.get_user_entities(uid)
        txt = services.format_webhook_links(user['secret_token'], ents)
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())

    elif data == 'gen_token':
        new_token = secrets.token_hex(8)
        services.update_user_token(uid, new_token)
        await query.edit_message_text(f"✅ تم تحديث الرمز: <code>{new_token}</code>", parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())

    # --- 3. لوحة التحكم (للأدمن) ---
    elif data.startswith(('admin_', 'gen_days_', 'manage_', 'adm_')):
        if int(uid) != ADMIN_ID: return
        if data == 'admin_panel': await admin.show_admin_panel(update, context)
        elif data.startswith('gen_days_'):
            days = int(data.split('_')[-1])
            await admin.process_generate_code(update, days)
        # بقية معالجات admin...

# --- دالة معالجة الرسائل (مع الحماية المتطورة) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    user_fullname = update.effective_user.full_name
    
    # ربط القنوات عبر مشاركة الشات
    if update.message.chat_shared:
        tid = str(update.message.chat_shared.chat_id)
        services.add_entity(uid, tid)
        await update.message.reply_text(f"✅ تم ربط القناة: {tid}", reply_markup=ReplyKeyboardRemove())
        return await check_activation_logic(update, context)

    text = update.message.text
    if not text: return

    # 1. فحص الحظر المسبق
    is_blocked, minutes = security.is_user_blocked(uid)
    if is_blocked:
        await update.message.reply_text(f"🚫 حسابك مقيد. يرجى المحاولة بعد {minutes} دقيقة.")
        return

    # 2. فحص المحتوى الخبيث (حقن SQL / روابط)
    if security.check_malicious_content(text):
        security.force_block_user(uid)
        alert = (f"🛡️ <b>اكتشاف محاولة تخريب!</b>\n\n👤 {user_fullname}\n🆔 <code>{uid}</code>\n📝 النص: <code>{text}</code>")
        await context.bot.send_message(chat_id=ADMIN_ID, text=alert, parse_mode='HTML')
        await update.message.reply_text("🚫 تم حظرك نهائياً لمخالفة سياسة الأمان.")
        return

    # 3. معالجة أكواد التفعيل
    if text.upper().startswith("MHO-") or context.user_data.get('state') == 'WAIT_CODE':
        code = text.upper().strip()
        success, days = await activate_with_code(uid, code)
        
        if success:
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ تم تفعيل اشتراكك بنجاح لمدة {days} يوم!")
            return await check_activation_logic(update, context)
        else:
            is_now_blocked, block_msg, attempts = security.log_failed_attempt(uid)
            if is_now_blocked:
                report = (f"🚨 <b>تقرير حظر</b>\n\n👤 {user_fullname}\n🆔 <code>{uid}</code>\n⚠️ {block_msg}\n🔑 الكود: <code>{text}</code>")
                await context.bot.send_message(chat_id=ADMIN_ID, text=report, parse_mode='HTML')
                await update.message.reply_text(f"🚫 {block_msg}.")
            else:
                remaining = 3 - attempts
                await update.message.reply_text(f"❌ الكود غير صحيح. متبقي لك ({remaining}) محاولات.")

async def check_activation_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot_me = await context.bot.get_me()
    
    if int(uid) == ADMIN_ID:
        await owner.bypass_subscription(uid)
        msg = "🌟 <b>مرحباً بك يا مِستر MOH</b>"
    else:
        user = services.get_user_data(uid)
        if not services.is_user_active(user):
            return await subscription.send_renewal_request(update, context, user_data=user)
        msg = "🏠 <b>القائمة الرئيسية:</b>"

    kb = await keyboards.get_main_menu(uid, bot_me.username)
    if update.callback_query: 
        await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)
    else: 
        await update.effective_chat.send_message(msg, reply_markup=kb, parse_mode=ParseMode.HTML)

# --- Flask Server (Webhook) ---
@app.route('/')
def index(): return "🚀 Sumou System Online", 200

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    # جلب البيانات الخام (Plain Text) دون أي تعديل
    raw_data = request.get_data(as_text=True)
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.user_id FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token=%s AND e.entity_id=%s AND u.is_activated=TRUE
            """, (token, target_id))
            if not cur.fetchone(): 
                return jsonify({"error": "Unauthorized"}), 403
    
    # إرسال البيانات الخام مباشرة للقناة
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                  json={"chat_id": target_id, "text": raw_data})
    
    return jsonify({"status": "sent"}), 200

if __name__ == "__main__":
    init_db.initialize_database()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات بالترتيب الصحيح
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    # معالج الرسائل يشمل كل شيء عدا الأوامر
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    # تشغيل سيرفر Flask والـ Keep Alive في خيوط منفصلة
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000))), daemon=True).start()
    threading.Thread(target=services.keep_alive, daemon=True).start()
    
    print("🚀 Bot is running...")
    application.run_polling(drop_pending_updates=True)
