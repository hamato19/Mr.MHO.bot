import logging, asyncio, secrets, os, re
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config, database, services, keyboards, web_server, privacy_policy
import activation_handler

# إعدادات المراقبة
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def clean_and_show_menu(update_or_query, context, uid):
    """تحديث القائمة الرئيسية بشكل سلس"""
    user = database.get_user_profile(uid)
    bot_info = await context.bot.get_me()
    is_owner = (str(uid) == str(config.ADMIN_ID))
    
    text = "🏠 <b>قائمة التحكم بـ سمو الأرقام:</b>"
    markup = await keyboards.get_main_menu(uid, bot_info.username)
    
    if not is_owner and (not user or not user.get('is_activated')):
        text = "⚠️ <b>حسابك غير مفعل حالياً.</b>\nيرجى الاشتراك أو إدخال كود التفعيل:"
        markup = keyboards.get_subscription_options()

    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
    else:
        try:
            await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        except Exception:
            await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = database.get_user_profile(uid)
    if not user:
        await update.message.reply_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
    else:
        await clean_and_show_menu(update, context, uid)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    is_owner = (str(uid) == str(config.ADMIN_ID))
    user = database.get_user_profile(uid)
    
    try: await query.answer()
    except: pass

    # --- إدارة التنقل ---
    if data == 'home':
        context.user_data.clear()
        await clean_and_show_menu(query, context, uid)
        return

    if data == 'view_priv':
        await query.edit_message_text(privacy_policy.DISCLAIMER_TEXT, parse_mode='HTML', reply_markup=keyboards.get_disclaimer_keyboard())
        return

    if data == 'accept_tos':
        database.register_user_if_not_exists(uid)
        await query.edit_message_text("✅ تم قبول الشروط.\nيرجى اختيار وسيلة التفعيل:", reply_markup=keyboards.get_subscription_options())
        return

    # زر التجديد/التفعيل (كان يحتاج تفعيل الحالة)
    if data == 'ren':
        await query.edit_message_text("🔄 <b>تجديد أو تفعيل الاشتراك:</b>\n\nمن فضلك أرسل كود التفعيل المكون من 12 خانة:", 
                                      parse_mode='HTML', reply_markup=keyboards.get_back_home())
        context.user_data['awaiting_code'] = True 
        return

    if data == 'check_by_id':
        await query.message.reply_text("🔎 من فضلك، أرسل الآن رقم الـ ID للتحقق من حالته:")
        context.user_data['awaiting_id_check'] = True
        return

    # --- لوحة الأدمن ---
    if is_owner:
        if data == 'adm':
            t, a, c = database.get_admin_dashboard_stats()
            await query.edit_message_text(f"👮 <b>لوحة الأدمن</b>\n\n👤 المستخدمين: {t}\n✅ المشتركين: {a}\n🎫 الأكواد النشطة: {c}", 
                                          parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
        
        elif data == 'adm_u':
            users = database.get_all_users()
            await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))
        
        elif data == 'adm_gen_menu':
            await query.edit_message_text("🔑 <b>توليد أكواد جديدة:</b>\nاختر مدة الصلاحية:", parse_mode='HTML', reply_markup=keyboards.get_generation_menu())
        
        elif data.startswith('gen_'):
            days = int(data.split('_')[1])
            code = f"SMO-{secrets.token_hex(4).upper()}"
            database.add_subscription_code(code, days)
            await query.message.reply_text(f"✅ <b>تم توليد كود جديد ({days} يوم):</b>\n\n<code>{code}</code>", parse_mode='HTML')
            await clean_and_show_menu(query, context, uid)

        elif data.startswith('view_u_'):
            target_id = data.replace('view_u_', '')
            u_details = database.get_user_profile(target_id)
            if u_details:
                await query.edit_message_text(f"👤 <b>إدارة:</b> <code>{target_id}</code>\nالحالة: {'نشط ✅' if u_details['is_activated'] else 'متوقف ❌'}", 
                                              parse_mode='HTML', reply_markup=keyboards.get_user_control_keyboard(target_id, u_details['is_activated']))
        
        elif data.startswith('toggle_u_'):
            parts = data.split('_')
            target_id, new_status = parts[2], (parts[1] == 'on')
            database.update_user_status(target_id, new_status)
            await query.answer(f"✅ تم {'تفعيل' if new_status else 'إيقاف'} الحساب")
            u_details = database.get_user_profile(target_id)
            await query.edit_message_reply_markup(reply_markup=keyboards.get_user_control_keyboard(target_id, u_details['is_activated']))

        elif data.startswith('del_u_'):
            target_id = data.replace('del_u_', '')
            database.delete_user(target_id) 
            await query.answer(f"🗑️ تم حذف المستخدم نهائياً", show_alert=True)
            users = database.get_all_users()
            await query.edit_message_text("👥 <b>تم تحديث القائمة:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))

        if data in ['adm', 'adm_u', 'adm_gen_menu'] or data.startswith(('gen_', 'view_u_', 'toggle_', 'del_')): return

    # --- وظائف المشتركين ---
    if is_owner or (user and user.get('is_activated')):
        if data == 'chs':
            ents = database.get_user_entities(uid)
            if not ents:
                await query.answer("⚠️ لا توجد قنوات مرتبطة حالياً", show_alert=True)
                return
            await query.edit_message_text("📋 <b>قنواتك المرتبطة:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))
        
        elif data == 'add_channel':
            await query.message.reply_text("📢 اضغط الزر أدناه لاختيار القناة المراد ربطها:", 
                                          reply_markup=keyboards.get_request_channel_keyboard())
            return
        
        elif data == 'wh':
            webhook_text = services.format_webhook_links(uid)
            await query.edit_message_text(f"🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n<code>{webhook_text}</code>", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        
        elif data == 'acc':
            expiry = services.get_time_remaining(user.get('expiry_date')) if user else "دائم"
            await query.edit_message_text(f"👤 <b>بيانات حسابك:</b>\n🆔 المعرف: <code>{uid}</code>\n⏳ الصلاحية: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        
        elif data.startswith('d_'):
            ch_id = data.replace('d_', '')
            database.delete_entity(uid, ch_id)
            await query.answer("✅ تم الحذف")
            ents = database.get_user_entities(uid)
            await query.edit_message_reply_markup(reply_markup=keyboards.get_entities_keyboard(ents))
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not update.message or (not update.message.text and not update.message.chat_shared): return
    text = update.message.text.strip() if update.message.text else ""

    # 1. ربط القنوات
    if update.message.chat_shared:
        database.add_user_entity(uid, update.message.chat_shared.chat_id, "Channel")
        await update.message.reply_text("✅ تم ربط القناة بنجاح!")
        await clean_and_show_menu(update, context, uid)
        return

    # 2. فحص المعرف (ID Check)
    if context.user_data.get('awaiting_id_check'):
        context.user_data['awaiting_id_check'] = False
        clean_id = ''.join(re.findall(r'\d+', text))
        if not clean_id:
            await update.message.reply_text("⚠️ يرجى إرسال رقم الـ ID بشكل صحيح.")
        else:
            u_prof = database.get_user_profile(clean_id)
            if u_prof and u_prof.get('is_activated'):
                await update.message.reply_text(f"✅ المعرف <code>{clean_id}</code> <b>نشط ومفعل</b>.", parse_mode='HTML')
            else:
                await update.message.reply_text(f"❌ المعرف <code>{clean_id}</code> غير موجود أو غير مفعل حالياً.", parse_mode='HTML')
        await clean_and_show_menu(update, context, uid)
        return

    # 3. معالجة أكواد التفعيل (سواء بدأت بـ SMO- أو كانت حالة انتظار)
    if text.upper().startswith("SMO-") or context.user_data.get('awaiting_code'):
        context.user_data['awaiting_code'] = False
        msg = await update.message.reply_text("⏳ جاري التحقق من الرمز...")
        success, result = activation_handler.process_activation(uid, text.upper())
        await msg.edit_text(f"{'🎉' if success else '❌'} {result}", parse_mode='HTML')
        if success: await clean_and_show_menu(update, context, uid)
        return

async def main():
    database.init_db()
    asyncio.create_task(web_server.start_server())
    app = Application.builder().token(config.BOT_TOKEN).read_timeout(30).connect_timeout(30).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.StatusUpdate.CHAT_SHARED, handle_message))
    
    logger.info("🚀 البوت يعمل الآن بكامل طاقته...")
    await app.initialize(); await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
