import os, secrets, asyncio, threading, logging, datetime, requests, time
from flask import Flask, request, jsonify
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- استيراد الملفات المساعدة (Modular Structure) ---
import config
import keyboards 
import services
import init_db
import security
import owner
import admin      
import terms
import subscription
import webhooks  # ملف الويب هوك المطور (خام)

from database import get_db
from auth import activate_with_code

# الإعدادات الأساسية
BOT_TOKEN = config.BOT_TOKEN
ADMIN_ID = config.ADMIN_ID

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. تشغيل البداية ---
@security.rate_limit(seconds=1)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    services.initialize_user(uid)
    
    if int(uid) == ADMIN_ID:
        return await check_activation_logic(update, context)
        
    welcome_msg = "👋 مرحباً بك في نظام سمو الأرقام\nالرجاء اختيار اللغة:\n\nWelcome! Please choose your language:"
    await update.effective_chat.send_message(welcome_msg, reply_markup=keyboards.get_language_keyboard())

# --- 2. معالج الأزرار الشامل (تفعيل جميع الأزرار والروابط) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    uid = update.effective_user.id
    await query.answer()

    # فحص الحظر (للأعضاء فقط)
    if int(uid) != ADMIN_ID:
        is_blocked, _ = security.is_user_blocked(uid)
        if is_blocked: return await query.answer("🚫 حسابك مقيد حالياً.", show_alert=True)

    # --- أ. أزرار الشروط واللغة ---
    if data.startswith('set_lang_'):
        lang = data.split('_')[2]
        await terms.send_terms(update, context, user_lang=lang)
    elif data == 'accept_terms':
        await terms.handle_terms_callback(update, context, check_activation_logic)
        
    elif data == 'home':
        await check_activation_logic(update, context)
    elif data == 'decline_terms':
        await query.edit_message_text("🚫 يجب الموافقة على الشروط لاستخدام خدماتنا.")

    # --- ب. إدارة الحساب والقنوات (قنواتي، ربط، حذف) ---
    elif data == 'acc':
        user = services.get_user_data(uid)
        time_left = services.get_time_remaining(user['expiry_date'])
        txt = f"👤 <b>بيانات الحساب:</b>\n\n• الحالة: {'فعال ✅' if user['is_activated'] else 'متوقف ❌'}\n• المتبقي: {time_left}"
        await query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())
        
    elif data == 'renew_sub':
        context.user_data['state'] = 'WAIT_CODE'
        await query.edit_message_text("📥 <b>أدخل كود التفعيل (MHO-xxxx) الآن:</b>", parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())

    elif data == 'add_ch': # ربط قناة جديدة
        await query.message.reply_text("📢 قم بإضافة البوت لقناتك كمشرف، ثم اضغط الزر لاختيار القناة:", reply_markup=keyboards.get_channel_request_keyboard())

    elif data == 'view_chs': # قنواتي
        ents = services.get_user_entities(uid)
        if not ents: return await query.edit_message_text("❌ لا توجد قنوات مرتبطة.", reply_markup=keyboards.get_back_to_home())
        await query.edit_message_text("📺 قنواتك (اضغط للحذف):", reply_markup=await keyboards.get_entities_keyboard(ents))

    elif data.startswith('del_ent_'): # حذف ربط قناة
        ent_id = data.replace('del_ent_', '')
        services.delete_entity(uid, ent_id)
        await query.answer("🗑️ تم حذف الربط بنجاح", show_alert=True)
        await check_activation_logic(update, context)

    # --- ج. نظام الويب هوك والرمز (روابط ويب هوك، توليد رمز) ---
    elif data == 'view_wh':
        await webhooks.show_webhook_links(update, context)
    elif data == 'gen_token':
        await webhooks.refresh_secret_token(update, context)

    # --- د. لوحة التحكم للمالك والأدمن ---
    elif data.startswith(('admin_', 'gen_days_', 'manage_', 'adm_')):
        if int(uid) != ADMIN_ID: return
        if data == 'admin_panel': await admin.show_admin_panel(update, context)
        elif data == 'admin_stats': await admin.show_admin_stats(update)
        elif data == 'admin_users': await admin.list_users(update)
        elif data.startswith('manage_'): await admin.manage_single_user(update, context, data.replace('manage_', ''))
        elif data.startswith('gen_days_'): await admin.process_generate_code(update, int(data.split('_')[-1]))
        elif data.startswith('adm_'):
            p = data.split('_')
            if len(p) >= 3: await admin.handle_admin_actions(update, context, p[1], p[2])

# --- 3. معالجة الرسائل ونتائج اختيار القنوات ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id

    # استقبال القناة المختارة (Chat Shared) لربطها
    if update.message and update.message.chat_shared:
        services.add_entity(uid, str(update.message.chat_shared.chat_id))
        return await update.message.reply_text("✅ تم ربط القناة بنجاح! توجه الآن لروابط الويب هوك.", reply_markup=keyboards.get_back_to_home())
    
    if not update.message or not update.message.text: return
    text = update.message.text.strip().upper()

    # نظام تفعيل الأكواد
    if text.startswith("MHO-") or context.user_data.get('state') == 'WAIT_CODE':
        success, days = await activate_with_code(uid, text)
        if success:
            context.user_data['state'] = None
            await update.message.reply_text(f"✅ تم التفعيل بنجاح لمدة {days} يوم!")
            return await check_activation_logic(update, context)
        await update.message.reply_text("❌ الكود خاطئ أو منتهي.")

# --- 4. منطق التحقق من الاشتراك واختيار القائمة ---
async def check_activation_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot_me = await context.bot.get_me()
    
    if int(uid) == ADMIN_ID:
        await owner.bypass_subscription(uid)
        msg, kb = "🌟 <b>لوحة تحكم المالك</b>", await keyboards.get_main_menu(uid, bot_me.username)
    else:
        user = services.get_user_data(uid)
        if not services.is_user_active(user):
            msg, kb = "🚫 <b>اشتراكك منتهي</b>", keyboards.get_renewal_keyboard()
        else:
            msg, kb = "🏠 <b>القائمة الرئيسية</b>", await keyboards.get_main_menu(uid, bot_me.username)

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await update.effective_chat.send_message(msg, reply_markup=kb, parse_mode=ParseMode.HTML)

# --- 5. تشغيل السيرفر والبوت ---
if __name__ == "__main__":
    init_db.initialize_database()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    # filters.ALL لضمان استلام نتائج اختيار القنوات (chat_shared)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    # تشغيل سيرفر الويب هوك (Flask) في ثريد منفصل لضمان استقبال إشارات TradingView خام
    threading.Thread(target=webhooks.run_server, daemon=True).start()
    
    print("🚀 Bot Sumou is Fully Linked & Online!")
    application.run_polling(drop_pending_updates=True)
