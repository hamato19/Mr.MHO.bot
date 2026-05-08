import logging, asyncio, secrets, os
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# استيراد الملفات (تأكد أن أسماء الملفات صحيحة في مجلدك)
import config, database, services, keyboards, web_server, privacy_policy, security

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def back_to_main_menu(update_or_query, context, uid):
    bot_info = await context.bot.get_me()
    markup = await keyboards.get_main_menu(uid, bot_info.username)
    text = "🏠 <b>القائمة الرئيسية:</b>"
    if isinstance(update_or_query, Update): 
        await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
    else: 
        await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)

@security.rate_limit(seconds=1)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    # حماية: فحص الحظر
    blocked, _, _ = security.is_user_blocked(uid)
    if blocked: return

    user = database.get_user_profile(uid)
    if not user:
        await update.message.reply_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
        return

    is_owner = (str(uid) == str(config.ADMIN_ID))
    if not is_owner and not user.get('is_activated'):
        await update.message.reply_text("⚠️ الاشتراك غير نشط. أرسل الكود الآن:", reply_markup=keyboards.get_subscription_options())
        context.user_data['awaiting_code'] = True
        return
    await back_to_main_menu(update, context, uid)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    try: await query.answer()
    except: pass

    try:
        # --- 1. نظام القبول والخصوصية ---
        if data == 'accept_tos':
            database.register_user_if_not_exists(uid)
            await query.edit_message_text("✅ تم قبول الشروط. أرسل كود التفعيل:", reply_markup=keyboards.get_subscription_options())
            context.user_data['awaiting_code'] = True
            return

        # --- 2. نظام المستخدم (الويب هوك والحماية) ---
        user = database.get_user_profile(uid)
        if data == 'home': await back_to_main_menu(query, context, uid)
        elif data == 'acc':
            expiry = services.get_time_remaining(user.get('expiry_date'))
            await query.edit_message_text(f"👤 <b>حسابك:</b>\n🆔 ID: <code>{uid}</code>\n⏳ ينتهي في: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'wh': # زر الويب هوك
            await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'tok': # تحديث رمز الأمان للحماية
            if database.update_user_secret_token(uid):
                await query.edit_message_text("✅ <b>تم تحديث رمز الأمان!</b>\nقم بتحديث روابطك في TradingView.", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'ren':
            await query.edit_message_text("🎫 أرسل كود التفعيل الآن:", reply_markup=keyboards.get_back_home())
            context.user_data['awaiting_code'] = True

        # --- 3. نظام لوحة الأدمن الكامل ---
        elif is_owner:
            if data == 'adm':
                t, a, c = database.get_admin_dashboard_stats()
                await query.edit_message_text(f"👮 <b>لوحة المالك</b>\n👤 الكل: {t} | ✅ نشط: {a}\n🎫 أكواد: {c}", reply_markup=keyboards.get_admin_keyboard())
            elif data == 'adm_u':
                users = database.get_all_users()
                await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>", reply_markup=keyboards.get_users_management_keyboard(users))
            elif data == 'adm_gen_menu':
                await query.edit_message_text("🔑 <b>توليد أكواد:</b>", reply_markup=keyboards.get_generation_menu())
            elif data.startswith('gen_'): # معالجة توليد الأكواد
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
                await query.answer("✅ تم التحديث")
                users = database.get_all_users()
                await query.edit_message_text("👥 تم التحديث:", reply_markup=keyboards.get_users_management_keyboard(users))

    except Exception as e: logger.error(f"Error in Callback: {e}")

async def main():
    database.init_db()
    # تشغيل سيرفر الويب لضمان استقرار Render ومنع الويب هوك من التعطل
    asyncio.create_task(web_server.start_server())
    
    app = Application.builder().token(config.BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await app.initialize(); await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("✅ النظام يعمل بكفاءة 100%")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
