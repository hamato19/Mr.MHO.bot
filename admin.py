import logging
import asyncio
import datetime
import secrets
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from database import get_db
from psycopg2.extras import RealDictCursor
import config

# --- 1. القائمة الرئيسية للأدمن ---
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    import keyboards 
    kb = keyboards.get_admin_main_keyboard()
    
    text = "👮 <b>لوحة تحكم المطور (أبو إلياس)</b>\n\nإدارة المستخدمين والاشتراكات والبيانات:"
    
    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await update.effective_chat.send_message(text, reply_markup=kb, parse_mode=ParseMode.HTML)

# --- 2. نظام توليد الأكواد ---
async def show_generate_code_menu(update: Update):
    query = update.callback_query
    import keyboards
    kb = keyboards.get_code_generation_keyboard()
    
    text = "🎫 <b>توليد كود تفعيل جديد:</b>\n\nاختر مدة الصلاحية للكود الذي تريد إنشاؤه:"
    await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def process_generate_code(update: Update, days: int):
    query = update.callback_query
    new_code = f"MHO-{secrets.token_hex(4).upper()}"
    
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO activation_codes (code, days_valid, is_used) VALUES (%s, %s, False)",
                    (new_code, days)
                )
                conn.commit()
        
        text = (f"✅ <b>تم توليد الكود بنجاح!</b>\n\n"
                f"🎫 الكود: <code>{new_code}</code>\n"
                f"⏳ المدة: {days} يوم\n\n"
                f"أرسل الكود للمستخدم لتفعيل حسابه.")
        
        kb = [[InlineKeyboardButton("🔄 توليد كود آخر", callback_data='admin_gen_codes')],
              [InlineKeyboardButton("🔙 عودة للوحة", callback_data='admin_panel')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Generate Code Error: {e}")
        await query.answer("❌ خطأ في قاعدة البيانات")

# --- 3. إدارة المستخدمين ---
async def list_users(update: Update):
    query = update.callback_query
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT user_id, is_activated FROM users ORDER BY created_at DESC LIMIT 15")
                users = cur.fetchall()
        
        text = "👥 <b>آخر 15 مستخدم مسجل:</b>\n\n"
        kb = []
        for u in users:
            status = "✅" if u['is_activated'] else "❌"
            text += f"• <code>{u['user_id']}</code> {status}\n"
            # هنا التعديل: callback مطابق لما في main.py
            kb.append([InlineKeyboardButton(f"⚙️ إدارة {u['user_id']}", callback_data=f"manage_{u['user_id']}")])
        
        kb.append([InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"List Users Error: {e}")

async def manage_single_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str):
    query = update.callback_query
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (str(user_id),))
                user = cur.fetchone()
        
        if not user: return await query.answer("❌ مستخدم غير موجود")

        status_txt = "نشط ✅" if user['is_activated'] else "غير مفعل ❌"
        # حماية في حال كان التاريخ None
        expiry = user['expiry_date'].strftime('%Y-%m-%d %H:%M') if user['expiry_date'] else "غير محدد"
        
        text = (f"👤 <b>إدارة المستخدم:</b> <code>{user_id}</code>\n\n"
                f"• الحالة: {status_txt}\n"
                f"• ينتهي في: <code>{expiry}</code>\n"
                f"• الرمز السري: <code>{user['secret_token']}</code>")
        
        # أزرار الأكشن: adm_Action_UserId
        kb = [
            [InlineKeyboardButton("✅ تفعيل 30 يوم", callback_data=f"adm_act_{user_id}"),
             InlineKeyboardButton("🚫 تعطيل", callback_data=f"adm_deact_{user_id}")],
            [InlineKeyboardButton("🗑️ حذف نهائي", callback_data=f"adm_del_{user_id}")],
            [InlineKeyboardButton("🔙 عودة للقائمة", callback_data='admin_users')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e: 
        logging.error(f"Manage User Error: {e}")

# --- 4. معالجة إجراءات الأدمن (تفعيل/تعطيل/حذف) ---
async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, user_id: str):
    query = update.callback_query
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                if action == 'act': # تفعيل
                    new_expiry = datetime.datetime.now() + datetime.timedelta(days=30)
                    cur.execute("UPDATE users SET is_activated = True, expiry_date = %s WHERE user_id = %s", (new_expiry, user_id))
                    msg = "✅ تم التفعيل لمدة 30 يوم"
                elif action == 'deact': # تعطيل
                    cur.execute("UPDATE users SET is_activated = False WHERE user_id = %s", (user_id,))
                    msg = "❌ تم تعطيل الحساب"
                elif action == 'del': # حذف
                    cur.execute("DELETE FROM entities WHERE user_id = %s", (user_id,))
                    cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
                    msg = "🗑️ تم حذف المستخدم وبياناته"
                conn.commit()
        
        await query.answer(msg, show_alert=True)
        # العودة لقائمة المستخدمين لتحديث العرض
        await list_users(update)
    except Exception as e: 
        logging.error(f"Admin Action Error: {e}")
        await query.answer("❌ فشل تنفيذ الإجراء")

# --- 5. الإحصائيات ---
async def show_admin_stats(update: Update):
    query = update.callback_query
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM users")
                total = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM users WHERE is_activated = True")
                active = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM entities")
                channels = cur.fetchone()[0]
        
        text = (f"📊 <b>إحصائيات نظام سمو الأرقام:</b>\n\n"
                f"• إجمالي المستخدمين: <code>{total}</code>\n"
                f"• المشتركين النشطين: <code>{active}</code>\n"
                f"• القنوات المرتبطة: <code>{channels}</code>")
        
        kb = [[InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Stats Error: {e}")
