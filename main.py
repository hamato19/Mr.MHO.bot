import logging, asyncio, secrets, os
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# استيراد الملفات الخاصة بك
import config, database, services, keyboards, web_server, privacy_policy, security

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def back_to_main_menu(update_or_query, context, uid):
    bot_info = await context.bot.get_me()
    markup = await keyboards.get_main_menu(uid, bot_info.username)
    text = "🏠 <b>القائمة الرئيسية للمنظومة:</b>"
    if isinstance(update_or_query, Update): 
        await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
    else: 
        await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)

@security.rate_limit(seconds=1)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    # حماية من الحظر
    blocked, _, _ = security.is_user_blocked(uid)
    if blocked: return

    user = database.get_user_profile(uid)
    if not user:
        await update.message.reply_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
        return

    is_owner = (str(uid) == str(config.ADMIN_ID))
    if not is_owner and not user.get('is_activated'):
        await update.message.reply_text("⚠️ الاشتراك غير نشط. أرسل كود التفعيل:", reply_markup=keyboards.get_subscription_options())
        context.user_data['awaiting_code'] = True
        return
    await back_to_main_menu(update, context, uid)

# --- هذه هي الدالة التي كانت ناقصة وتسببت في الخطأ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    # إذا كان البوت ينتظر كود تفعيل
    if context.user_data.get('awaiting_code'):
        days = database.check_and_use_code(text)
        if days:
            database.activate_user_subscription(uid, days)
            context.user_data['awaiting_code'] = False
            await update.message.reply_text(f"✅ تم تفعيل الاشتراك لمدة {days} يوم!", reply_markup=ReplyKeyboardRemove())
            await back_to_main_menu(update, context, uid)
        else:
            await update.message.reply_text("❌ الكود غير صحيح أو مستخدم مسبقاً.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    try: await query.answer()
    except: pass

    try:
        if data == 'accept_tos':
            database.register_user_if_not_exists(uid)
            await query.edit_message_text("✅ تم القبول. أرسل كود التفعيل الآن:", reply_markup=keyboards.get_subscription_options())
            context.user_data['awaiting_code'] = True
            return

        user = database.get_user_profile(uid)
        if data == 'home': await back_to_main_menu(query, context, uid)
        elif data == 'acc':
            expiry = services.get_time_remaining(user.get('expiry_date'))
            await query.edit_message_text(f"👤 حسابك:\n🆔 ID: <code>{uid}</code>\n⏳ الانتهاء: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'wh': # الويب هوك
            await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'tok': # تحديث رمز الأمان
            if database.update_user_secret_token(uid):
                await query.edit_message_text("✅ تم تحديث رمز الأمان بنجاح!", reply_markup=keyboards.get_back_home())
        elif data == 'ren':
            await query.edit_message_text("🎫 أرسل كود التفعيل الآن:", reply_markup=keyboards.get_back_home())
            context.user_data['awaiting_code'] = True

        # لوحة الأدمن
        elif is_owner:
            if data == 'adm':
                t, a, c = database.get_admin_dashboard_stats()
                await query.edit_message_text(f"👮 لوحة الأدمن\n👤 الكل: {t} | ✅ نشط: {a}\n🎫 أكواد: {c}", reply_markup=keyboards.get_admin_keyboard())
            elif data == 'adm_u':
                users = database.get_all_users()
                await query.edit_message_text("👥 إدارة المستخدمين:", reply_markup=keyboards.get_users_management_keyboard(users))
            elif data == 'adm_gen_menu':
                await query.edit_message_text("🔑 اختر مدة الكود:", reply_markup=keyboards.get_generation_menu())
            elif data.startswith('gen_'):
                days = int(data.split('_')[1])
                code = f"SMO-{secrets.token_hex(3).upper()}"
                if database.add_subscription_code(code, days):
                    await query.message.reply_text(f"🎫 كود جديد ({days} يوم):\n<code>{code}</code>", parse_mode='HTML')
            elif data.startswith('view_u_'):
                tid = data.split('_')[2]
                u = database.get_user_details(tid)
                await query.edit_message_text(f"👤 إدارة {tid}:", reply_markup=keyboards.get_user_control_keyboard(tid, u['is_activated']))
            elif data.startswith('toggle_u_'):
                _, _, action, tid = data.split('_')
                database.update_user_status(tid, action == 'activate')
                users = database.get_all_users()
                await query.edit_message_text("✅ تم التحديث:", reply_markup=keyboards.get_users_management_keyboard(users))

    except Exception as e: logger.error(f"Error: {e}")

async def main():
    database.init_db()
    asyncio.create_task(web_server.start_server())
    
    app = Application.builder().token(config.BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    # الآن handle_message معرفة ولن يحدث خطأ
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await app.initialize(); await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("✅ النظام يعمل الآن بدون أخطاء")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
