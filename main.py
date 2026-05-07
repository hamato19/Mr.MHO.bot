import os
import asyncio
import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters, 
    ContextTypes
)

# --- استيراد ملفاتك الخاصة ---
import config
import keyboards 
import services
import init_db
import security
import admin      
import terms
import web_server # ملف aiohttp الجديد

# الإعدادات الأساسية
BOT_TOKEN = config.BOT_TOKEN
ADMIN_ID = config.ADMIN_ID

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. دالة البداية /start ---
@security.rate_limit(seconds=1)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    services.initialize_user(uid)
    
    # دخول المالك مباشرة
    if int(uid) == ADMIN_ID:
        return await check_activation_logic(update, context)
        
    welcome_msg = "👋 مرحباً بك في نظام سمو الأرقام\nالرجاء اختيار اللغة:\n\nWelcome! Please choose your language:"
    await update.effective_chat.send_message(welcome_msg, reply_markup=keyboards.get_language_keyboard())

# --- 2. معالج الأزرار (CallbackQuery) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    await query.answer()

    # فحص الحظر
    if int(uid) != ADMIN_ID:
        is_blocked, _ = security.is_user_blocked(uid)
        if is_blocked: return await query.answer("🚫 حسابك مقيد حالياً.", show_alert=True)

    # الأزرار الأساسية
    if data.startswith('set_lang_'):
        lang = data.split('_')[2]
        await terms.send_terms(update, context, user_lang=lang)
    elif data == 'accept_terms':
        await terms.handle_terms_callback(update, context, check_activation_logic)
    elif data == 'home':
        await check_activation_logic(update, context)
    
    # بيانات الحساب
    elif data == 'acc':
        user = services.get_user_data(uid)
        time_left = services.get_time_remaining(user['expiry_date'])
        txt = f"👤 <b>بيانات الحساب:</b>\n\n• الحالة: {'فعال ✅' if user['is_activated'] else 'متوقف ❌'}\n• المتبقي: {time_left}"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())
        
    elif data == 'renew_sub':
        context.user_data['state'] = 'WAIT_CODE'
        await query.edit_message_text("📥 <b>أدخل كود التفعيل (MHO-xxxx) الآن:</b>", parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())

    # القنوات المرتبطة
    elif data == 'view_chs':
        ents = services.get_user_entities(uid)
        if not ents: 
            return await query.edit_message_text("❌ لا توجد قنوات مرتبطة بحسابك.", reply_markup=keyboards.get_back_to_home())
        await query.edit_message_text("📺 قنواتك المرتبطة (اضغط للحذف):", reply_markup=keyboards.get_entities_keyboard(ents))

    elif data.startswith('del_ent_'):
        ent_id = data.replace('del_ent_', '')
        services.delete_entity(uid, ent_id)
        await query.answer("🗑️ تم حذف الربط بنجاح", show_alert=True)
        await check_activation_logic(update, context)

    elif data == 'add_ch':
        await query.message.reply_text("📢 قم بإضافة البوت لقناتك كمشرف، ثم اضغط الزر لاختيار القناة:", reply_markup=keyboards.get_channel_request_keyboard())

    # أوامر الأدمن
    elif data.startswith(('admin_', 'gen_days_', 'manage_')):
        if int(uid) == ADMIN_ID:
            await admin.handle_callback_logic(update, context, data)

# --- 3. معالجة الرسائل والقنوات المختارة ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id

    # استقبال القناة المختارة
    if update.message and update.message.chat_shared:
        chat_id = update.message.chat_shared.chat_id
        try:
            chat_info = await context.bot.get_chat(chat_id)
            chat_title = chat_info.title
        except:
            chat_title = f"قناة {chat_id}"
        services.add_entity(uid, str(chat_id), chat_title)
        return await update.message.reply_text(f"✅ تم ربط <b>{chat_title}</b> بنجاح!", parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())
    
    if not update.message or not update.message.text: return
    text = update.message.text.strip().upper()

    # معالجة الأكواد
    if text.startswith("MHO-") or context.user_data.get('state') == 'WAIT_CODE':
        success, msg = services.redeem_code(uid, text)
        await update.message.reply_text(msg)
        if success:
            context.user_data['state'] = None
            return await check_activation_logic(update, context)

# --- 4. منطق القوائم الرئيسية ---
async def check_activation_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot_info = await context.bot.get_me()
    
    if int(uid) == ADMIN_ID:
        msg, kb = "🌟 <b>لوحة تحكم المالك</b>", await keyboards.get_main_menu(uid, bot_info.username)
    else:
        user = services.get_user_data(uid)
        if not services.is_user_active(user):
            msg, kb = "🚫 <b>اشتراكك منتهي أو غير مفعل</b>", keyboards.get_renewal_keyboard()
        else:
            msg, kb = "🏠 <b>القائمة الرئيسية</b>", await keyboards.get_main_menu(uid, bot_info.username)

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await update.effective_chat.send_message(msg, reply_markup=kb, parse_mode=ParseMode.HTML)

# --- 5. الهيكل التشغيلي (Main Entry Point) ---
async def main():
    # 1. تهيئة قاعدة البيانات
    try:
        init_db.initialize_database()
    except Exception as e:
        logging.error(f"❌ DB Error: {e}")

    # 2. تشغيل السيرفر الموحد (aiohttp)
    await web_server.start_server()

    # 3. بناء تطبيق التليجرام
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 4. إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    # 5. تشغيل البوت يدوياً داخل الـ Loop لضمان الاستقرار
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        
        print("🚀 Bot Sumou Al Arqam is ONLINE & READY!")
        
        # الانتظار اللانهائي
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("🔴 تم إيقاف النظام.")
