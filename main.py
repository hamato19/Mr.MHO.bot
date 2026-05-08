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

    # نظام حماية الحظر
    blocked, _, _ = security.is_user_blocked(uid)
    if blocked: return

    try:
        # 1. قسم سياسة الخصوصية
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

        # 2. القائمة الرئيسية والويب هوك
        if data == 'home':
            await back_to_main_menu(query, context, uid)
        elif data == 'acc':
            status = "✅ مفعل" if is_activated else "❌ غير مفعل"
            expiry = services.get_time_remaining(user.get('expiry_date')) if user else "غير محدود"
            await query.edit_message_text(f"👤 <b>بيانات الحساب:</b>\n🆔 ID: <code>{uid}</code>\n🚦 الحالة: {status}\n⏳ المتبقي: {expiry}", parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'wh':
            await query.edit_message_text(services.format_webhook_links(uid), parse_mode='HTML', reply_markup=keyboards.get_back_home())
        elif data == 'tok':
            new_tok = secrets.token_hex(16)
            if database.update_user_secret_token(uid): # تم التصحيح لاسم الدالة في database.py
                await query.answer("✅ تم تحديث رمز الأمان بنجاح")
                await query.edit_message_text("🔐 <b>تحديث أمني ناجح</b>\nلقد تم توليد رمز جديد بنجاح.", parse_mode='HTML', reply_markup=keyboards.get_back_home())

        elif data == 'ren':
            await query.edit_message_text("🎫 أرسل كود التفعيل الجديد:", reply_markup=keyboards.get_back_home())
            context.user_data['awaiting_code'] = True
        elif data == 'add_channel':
            await query.message.reply_text("📢 اختر القناة المراد ربطها:", reply_markup=keyboards.get_request_channel_keyboard())
        elif data == 'chs':
            ents = database.get_user_entities(uid)
            await query.edit_message_text("📋 <b>إدارة القنوات:</b>", parse_mode='HTML', reply_markup=keyboards.get_entities_keyboard(ents))

        # 3. إدارة لوحة الأدمن (حصري للمالك)
        elif is_owner:
            if data == 'adm':
                t, a, c = database.get_admin_dashboard_stats()
                await query.edit_message_text(f"👮 <b>لوحة المالك</b>\n\n👥 الكل: {t} | ✅ النشط: {a}\n🎫 أكواد: {c}", parse_mode='HTML', reply_markup=keyboards.get_admin_keyboard())
            
            elif data == 'adm_u':
                users = database.get_all_users()
                if not users: await query.answer("📋 القائمة فارغة", show_alert=True)
                else: await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))

            elif data.startswith('view_u_'):
                target_id = data.split('_')[2]
                user_info = database.get_user_details(target_id)
                if user_info:
                    status = "✅ مفعل" if user_info['is_activated'] else "❌ معطل"
                    expiry = user_info['expiry_date'] or "غير محدود"
                    text = f"👤 <b>تفاصيل:</b>\n🆔 ID: <code>{target_id}</code>\n📊 الحالة: {status}\n📅 الانتهاء: {expiry}"
                    await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboards.get_user_control_keyboard(target_id, user_info['is_activated']))

            elif data.startswith('toggle_u_'):
                parts = data.split('_')
                action = parts[2]
                target_uid = parts[3]
                new_status = (action == 'activate')
                if database.update_user_status(target_uid, new_status):
                    await query.answer("✅ تم التحديث")
                    users = database.get_all_users()
                    await query.edit_message_text("👥 <b>إدارة المستخدمين:</b>", parse_mode='HTML', reply_markup=keyboards.get_users_management_keyboard(users))

            elif data.startswith('gen_'):
                days = int(data.split('_')[1])
                new_code = f"SMO-{secrets.token_hex(4).upper()}"
                if database.add_subscription_code(new_code, days):
                    await query.message.reply_text(f"🎫 كود جديد: <code>{new_code}</code>")

    except Exception as e:
        logging.error(f"Callback Error: {e}")
        await query.answer("🔴 حدث خطأ أثناء المعالجة")

# ... (باقي الدوال handle_message و handle_chat_shared و main تبقى كما هي)
