import logging
import asyncio
import secrets
import os
from telegram import Update
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

    is_owner = (str(uid) == str(config.ADMIN_ID))
    if not is_owner and not user.get('is_activated'):
        await update.message.reply_text("⚠️ <b>الحساب غير نشط</b>\nيرجى إرسال كود التفعيل:", parse_mode='HTML', reply_markup=keyboards.get_subscription_options())
        context.user_data['awaiting_code'] = True
        return

    await back_to_main_menu(update, context, uid)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة النصوص المرسلة (أكواد التفعيل)"""
    uid = update.effective_user.id
    text = update.message.text.strip()

    if context.user_data.get('awaiting_code'):
        # التحقق من الكود في قاعدة البيانات
        days = database.check_and_use_code(text)
        if days:
            database.activate_user_subscription(uid, days)
            context.user_data['awaiting_code'] = False
            await update.message.reply_text(f"✅ تم تفعيل الاشتراك بنجاح لمدة {days} يوم!", reply_markup=ReplyKeyboardRemove())
            await back_to_main_menu(update, context, uid)
        else:
            await update.message.reply_text("❌ الكود غير صحيح أو مستخدم مسبقاً. حاول مرة أخرى:")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    try: await query.answer()
    except: pass

    blocked, _, _ = security.is_user_blocked(uid)
    if blocked: return

    try:
        # 1. إدارة الخصوصية
        if data in ['view_priv', 'back_tos', 'accept_tos']:
            if data == 'accept_tos':
                database.register_user_if_not_exists(uid)
                await query.edit_message_text("✅ تم قبول الشروط. أرسل كود التفعيل الآن:", reply_markup=keyboards.get_subscription_options())
                context.user_data['awaiting_code'] = True
            return

        # 2. الخدمات (تعمل فقط للمفعلين أو المالك)
        user = database.get_user_profile(uid)
        if data == 'home':
            await back_to_main_menu(query, context, uid)
        elif data == 'wh':
            await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())
        
        # 3. لوحة تحكم المالك
        elif is_owner:
            if data == 'adm':
                t, a, c = database.get_admin_dashboard_stats()
                await query.edit_message_text(f"👮 <b>لوحة المالك</b>\n👥 الكل: {t} | ✅ النشط: {a}", parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
            elif data == 'adm_u':
                users = database.get_all_users()
                await query.edit_message_text("👥 إدارة المستخدمين:", reply_markup=keyboards.get_users_management_keyboard(users))
            elif data.startswith('view_u_'):
                target_id = data.split('_')[2]
                u_info = database.get_user_details(target_id)
                if u_info:
                    # تأكد أن هذه الدالة تستخدم callback_data وليس callback_query_data
                    await query.edit_message_text(f"👤 تفاصيل ID: {target_id}", reply_markup=keyboards.get_user_control_keyboard(target_id, u_info['is_activated']))

    except Exception as e:
        logger.error(f"Callback Error: {e}")

async def main():
    database.init_db()
    
    # بناء التطبيق
    app = Application.builder().token(config.BOT_TOKEN).concurrent_updates(True).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # تشغيل سيرفر الويب (Render)
    asyncio.create_task(web_server.start_server())
    
    # تشغيل البوت
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("✅ المنظومة تعمل الآن بكفاءة...")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
