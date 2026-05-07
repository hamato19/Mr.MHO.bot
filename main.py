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

    if data == 'home':
        await back_to_main_menu(query, context, uid)
    elif data == 'acc':
        status = "✅ مفعل" if is_activated else "❌ غير مفعل"
        expiry = services.get_time_remaining(user.get('expiry_date')) if user else "غير محدود"
        await query.edit_message_text(f"👤 <b>بيانات الحساب:</b>\n🆔 ID: <code>{uid}</code>\n🚦 الحالة: {status}\n⏳ المتبقي: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
    elif data == 'wh':
        await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())
    elif data == 'ren':
        await query.edit_message_text("🎫 أرسل كود التفعيل الجديد:", reply_markup=keyboards.get_back_home())
        context.user_data['awaiting_code'] = True
    elif data == 'add_channel':
        await query.message.reply_text("📢 اختر القناة المراد ربطها:", reply_markup=keyboards.get_request_channel_keyboard())
    elif data == 'chs':
        ents = database.get_user_entities(uid)
        await query.edit_message_text("📋 <b>إدارة القنوات:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))

    # --- إدارة لوحة الأدمن (المنطقة التي كان بها الخطأ) ---
    elif is_owner:
        if data == 'adm':
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 <b>لوحة المالك</b>\n\n👥 الكل: {t} | ✅ النشط: {a}\n🎫 أكواد: {c}", parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
        
        elif data == 'adm_u': # تم تصحيح الإزاحة هنا
            users = database.get_all_users()
            if not users:
                await query.answer("📋 لا يوجد مستخدمين", show_alert=True)
            else:
                await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>", reply_markup=keyboards.get_users_management_keyboard(users))

        elif data == 'adm_s': # تم تصحيح الإزاحة هنا
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"📊 <b>إحصائيات المنظومة:</b>\n\nالمستخدمين: {t}\nالمشتركين: {a}\nالأكواد المتوفرة: {c}", parse_mode='HTML', reply_markup=keyboards.get_back_to_admin())

        elif data == 'adm_gen_menu':
            await query.edit_message_text("🗓️ <b>توليد كود:</b>", reply_markup=keyboards.get_generation_menu())
            
        elif data.startswith('gen_'):
            days = int(data.split('_')[1])
            new_code = f"SMO-{secrets.token_hex(4).upper()}"
            if database.add_subscription_code(new_code, days):
                await query.message.reply_text(f"🎫 كود جديد: <code>{new_code}</code>")
                t, a, c = database.get_admin_dashboard_stats()
                await query.edit_message_text(f"👮 لوحة المالك\n✅ تم التوليد بنجاح.", reply_markup=keyboards.get_admin_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    uid = update.effective_user.id
    if update.message.text == "🔙 إلغاء":
        context.user_data['awaiting_code'] = False
        await back_to_main_menu(update, context, uid)
        return
    if context.user_data.get('awaiting_code'):
        if await security.process_security_check(update, context, uid, update.message.text):
            context.user_data['awaiting_code'] = False
            await back_to_main_menu(update, context, uid)

async def handle_chat_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_shared:
        uid = update.effective_user.id
        cid = update.message.chat_shared.chat_id
        try:
            chat = await context.bot.get_chat(cid)
            if database.add_entity(uid, str(cid), chat.title):
                await update.message.reply_text(f"✅ تم ربط: {chat.title}")
                await back_to_main_menu(update, context, uid)
        except:
            await update.message.reply_text("❌ تأكد من وجود البوت كأدمن بالقناة.")

async def main():
    database.init_db()
    app = Application.builder().token(config.BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_chat_shared))
    asyncio.create_task(web_server.start_server())
    asyncio.create_task(services.keep_alive())
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
