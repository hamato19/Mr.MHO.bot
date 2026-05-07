import logging
import asyncio
import secrets
import telegram
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# استيراد الملفات المحلية
import config
import database
import services
import keyboards 
import web_server
import privacy_policy  # ملف السياسة الجديد

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 1. الدالة الرئيسية /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = database.get_user_profile(uid)
    
    # 🛑 القفل الإجباري: إذا لم يوافق المستخدم مسبقاً (غير موجود بالقاعدة)
    if not user:
        await update.message.reply_text(
            privacy_policy.DISCLAIMER_TEXT, 
            parse_mode='HTML', 
            reply_markup=keyboards.get_disclaimer_keyboard()
        )
        return

    # إذا كان مسجلاً مسبقاً تظهر القائمة الرئيسية
    bot_info = await context.bot.get_me()
    markup = await keyboards.get_main_menu(uid, bot_info.username)
    
    welcome_text = (
        "👋 <b>مرحباً بك مجدداً في منظومة سمو الأرقام (Mr. MOH)</b>\n\n"
        "استخدم القائمة أدناه لإدارة حسابك وروابط الويب هوك القوية."
    )
    await update.message.reply_text(welcome_text, parse_mode='HTML', reply_markup=markup)

# --- 2. معالج الأزرار الشامل (Callbacks) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    
    try: await query.answer()
    except: pass

    # --- أزرار اتفاقية الاستخدام والخصوصية ---
    if data == 'view_priv':
        await query.edit_message_text(
            privacy_policy.PRIVACY_TEXT, 
            parse_mode='HTML', 
            reply_markup=keyboards.get_back_to_tos()
        )

    elif data == 'back_tos':
        await query.edit_message_text(
            privacy_policy.DISCLAIMER_TEXT, 
            parse_mode='HTML', 
            reply_markup=keyboards.get_disclaimer_keyboard()
        )

    elif data == 'reject_tos':
        await query.answer("⚠️ يجب الموافقة للمتابعة واستخدام البوت", show_alert=True)
        await query.message.delete()
        await start(update, context) # إعادة إرسال رسالة البداية

    elif data == 'accept_tos':
        database.register_user_if_not_exists(uid)
        subscription_text = (
            "✅ <b>شكرًا لموافقتك على الشروط.</b>\n\n"
            "حسابك الآن جاهز، لكنه يحتاج إلى تفعيل.\n"
            "يرجى إدخال كود التفعيل أو التواصل مع الإدارة للاشتراك:"
        )
        await query.edit_message_text(
            subscription_text, 
            parse_mode='HTML', 
            reply_markup=keyboards.get_subscription_options()
        )
        welcome_note = "👋 <b>مرحباً بك في عائلة سمو الأرقام!</b>"
        await context.bot.send_message(chat_id=uid, text=welcome_note, parse_mode='HTML')

    # --- التنقل والقائمة الرئيسية ---
    elif data == 'home':
        bot_info = await context.bot.get_me()
        markup = await keyboards.get_main_menu(uid, bot_info.username)
        await query.edit_message_text("🏠 <b>القائمة الرئيسية:</b>", parse_mode='HTML', reply_markup=markup)

    elif data == 'wh':
        msg_text = services.format_webhook_links(uid)
        await query.edit_message_text(msg_text, parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'acc':
        user = database.get_user_profile(uid)
        if user:
            status = "✅ مفعل" if user.get('is_activated') else "❌ غير مفعل"
            expiry = services.get_time_remaining(user.get('expiry_date'))
            acc_text = f"👤 <b>بيانات حسابك:</b>\n\n🆔 معرفك: <code>{uid}</code>\n🚦 الحالة: {status}\n⏳ المتبقي: {expiry}"
            await query.edit_message_text(acc_text, parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data == 'chs':
        entities = database.get_user_entities(uid)
        markup = keyboards.get_entities_keyboard(entities)
        await query.edit_message_text("📺 <b>قنواتك المرتبطة:</b>", parse_mode='HTML', reply_markup=markup)

    # --- أزرار لوحة التحكم للأدمن ---
    elif data == 'adm':
        if int(uid) == int(config.ADMIN_ID):
            total_u, active_u, codes = database.get_admin_dashboard_stats()
            admin_text = f"👮 <b>لوحة التحكم</b>\n\n👥 المستخدمين: {total_u}\n✅ النشطين: {active_u}\n🎫 الأكواد: {codes}"
            await query.edit_message_text(admin_text, parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())

    elif data == 'adm_gen_menu':
        await query.edit_message_text("🗓️ <b>اختر مدة الاشتراك للكود الجديد:</b>", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())

    elif data.startswith('gen_'):
        days = int(data.split('_')[1])
        random_part = secrets.token_hex(4).upper()
        new_code = f"SMO-{random_part}"
        if database.add_subscription_code(new_code, days):
            await query.message.reply_text(f"🎫 <b>تم توليد كود جديد ({days} يوم):</b>\n<code>{new_code}</code>", parse_mode='HTML')

    elif data == 'adm_u':
        users = database.get_all_users()
        if not users:
            await query.edit_message_text("∅ لا يوجد مستخدمين.", reply_markup=keyboards.get_back_home())
            return
        users_list = "👥 <b>قائمة آخر 20 مستخدم:</b>\n\n"
        for u in users:
            status = "✅" if u['is_activated'] else "❌"
            users_list += f"{status} <code>{u['user_id']}</code>\n"
        await query.edit_message_text(users_list, parse_mode='HTML', reply_markup=keyboards.get_back_home())

    elif data.startswith('d_'):
        target_id = data.replace('d_', '')
        database.delete_entity(uid, target_id)
        await query.answer("✅ تم الحذف")
        new_entities = database.get_user_entities(uid)
        await query.edit_message_reply_markup(reply_markup=keyboards.get_entities_keyboard(new_entities))

# --- 3. معالج الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    if update.message.chat_shared:
        channel_id = update.message.chat_shared.chat_id
        try:
            chat_info = await context.bot.get_chat(channel_id)
            if database.add_entity(uid, str(channel_id), chat_info.title):
                await update.message.reply_text(f"✅ تم ربط: <b>{chat_info.title}</b>", parse_mode='HTML', reply_markup=ReplyKeyboardRemove())
        except:
            await update.message.reply_text("❌ خطأ في الصلاحيات.", reply_markup=ReplyKeyboardRemove())
        return

    if context.user_data.get('awaiting_code'):
        success, msg = database.activate_user_with_code(uid, update.message.text.strip())
        context.user_data['awaiting_code'] = False
        bot_info = await context.bot.get_me()
        await update.message.reply_text(msg, reply_markup=await keyboards.get_main_menu(uid, bot_info.username))

# --- 4. التشغيل ---
async def main():
    database.init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    asyncio.create_task(web_server.start_server())
    asyncio.create_task(services.keep_alive())
    
    logger.info("🚀 النظام يعمل...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
