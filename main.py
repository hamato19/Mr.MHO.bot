import logging
import asyncio
import secrets
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# استيراد ملفات المنظومة
import config
import database
import services
import keyboards 
import web_server
import privacy_policy
import security  

# ضبط السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
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
    blocked, hours_left, level = security.is_user_blocked(uid)
    if blocked:
        msg = f"🔒 حسابك محظور. المتبقي: {hours_left} ساعة." if level < 3 else "🚫 حظر نهائي."
        await update.message.reply_text(msg)
        return

    user = database.get_user_profile(uid)
    if not user:
        await update.message.reply_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
        return

    if not (int(uid) == int(config.ADMIN_ID)) and not user.get('is_activated'):
        await update.message.reply_text("⚠️ <b>الحساب غير نشط</b>\nيرجى إرسال كود التفعيل:", parse_mode='HTML', reply_markup=keyboards.get_subscription_options())
        context.user_data['awaiting_code'] = True
        return

    await back_to_main_menu(update, context, uid)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (int(uid) == int(config.ADMIN_ID))
    
    try: await query.answer()
    except: pass

    blocked, _, _ = security.is_user_blocked(uid)
    if blocked: return

    try:
        # 1. إدارة الخصوصية والشروط
        if data in ['view_priv', 'back_tos', 'accept_tos', 'reject_tos']:
            if data == 'view_priv':
                await query.edit_message_text(privacy_policy.PRIVACY_TEXT, parse_mode='HTML', reply_markup=keyboards.get_back_to_tos())
            elif data == 'back_tos':
                await query.edit_message_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
            elif data == 'accept_tos':
                database.register_user_if_not_exists(uid)
                await query.edit_message_text("✅ تم قبول الشروط. أرسل كود التفعيل الآن:", reply_markup=keyboards.get_subscription_options())
                context.user_data['awaiting_code'] = True
            return

        user = database.get_user_profile(uid)
        is_activated = user.get('is_activated') if user else False

        if not is_owner and not is_activated:
            await query.answer("⚠️ الاشتراك غير نشط!", show_alert=True)
            return

        # 2. الخدمات والويب هوك
        if data == 'home':
            await back_to_main_menu(query, context, uid)
        elif data == 'acc':
            status = "✅ مفعل" if is_activated else "❌ غير مفعل"
            expiry = services.get_time_remaining(user.get('expiry_date')) if user else "غير محدود"
            await query.edit_message_text(f"👤 <b>بيانات الحساب:</b>\n🆔 ID: <code>{uid}</code>\n🚦 الحالة: {status}\n⏳ المتبقي: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'wh':
            await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'tok':
            if database.update_user_secret_token(uid):
                await query.answer("✅ تم تحديث رمز الأمان")
                await query.edit_message_text("🔐 <b>تحديث أمني ناجح</b>\nلقد تم توليد رمز جديد بنجاح.", parse_mode='HTML', reply_markup=keyboards.get_back_home())

        # 3. لوحة تحكم المالك
        elif is_owner:
            if data == 'adm':
                t, a, c = database.get_admin_dashboard_stats()
                await query.edit_message_text(f"👮 <b>لوحة المالك</b>\n\n👥 الكل: {t} | ✅ النشط: {a}\n🎫 أكواد: {c}", parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
            elif data == 'adm_u':
                users = database.get_all_users()
                if not users: await query.answer("📋 القائمة فارغة")
                else: await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))
            elif data.startswith('view_u_'):
                target_id = data.split('_')[2]
                u_info = database.get_user_details(target_id)
                if u_info:
                    await query.edit_message_text(f"👤 تفاصيل ID: {target_id}", reply_markup=keyboards.get_user_control_keyboard(target_id, u_info['is_activated']))
            elif data.startswith('toggle_u_'):
                _, _, action, t_uid = data.split('_')
                if database.update_user_status(t_uid, (action == 'activate')):
                    await query.answer("✅ تم التحديث")
                    users = database.get_all_users()
                    await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))

    except Exception as e:
        logger.error(f"Callback Error: {e}")
        await query.answer("🔴 حدث خطأ أثناء المعالجة")

async def main():
    database.init_db()
    app = Application.builder().token(config.BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    # ... بقية الـ Handlers ...
    asyncio.create_task(web_server.start_server())
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
