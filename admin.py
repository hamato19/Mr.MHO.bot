# admin.py
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
    
    # إضافة زر استعراض الأكواد للقائمة إذا لم يكن موجوداً في الكيبورد الأساسي
    # kb.inline_keyboard.insert(1, [InlineKeyboardButton("📜 الأكواد غير المستخدمة", callback_data='admin_view_codes')])
    
    text = "👮 <b>لوحة تحكم المطور (أبو إلياس)</b>\n\nإدارة المستخدمين والاشتراكات والبيانات:"
    
    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await update.effective_chat.send_message(text, reply_markup=kb, parse_mode=ParseMode.HTML)

# --- 2. نظام توليد الأكواد وعرضها ---
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

async def show_unused_codes(update: Update):
    """عرض الأكواد التي لم يتم تفعيلها بعد"""
    query = update.callback_query
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # التأكد من ترتيب الأكواد من الأحدث للأقدم
                cur.execute("SELECT code, days_valid FROM activation_codes WHERE is_used = False ORDER BY id DESC")
                codes = cur.fetchall()
        
        if not codes:
            return await query.answer("لا توجد أكواد غير مستخدمة حالياً.", show_alert=True)

        text = "🎫 <b>أكواد التفعيل المتوفرة:</b>\n\n"
        for c in codes:
            text += f"• <code>{c['code']}</code> ({c['days_valid']} يوم)\n"
        
        kb = [[InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"List Codes Error: {e}")
        await query.answer("❌ حدث خطأ أثناء جلب الأكواد.")

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
            kb.append([InlineKeyboardButton(f"⚙️ إدارة {u['user_id']}", callback_data=f"manage_user_{u['user_id']}")])
        
        kb.append([InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"List Users Error: {e}")

async def manage_single_user(update: Update, user_id: str):
    query = update.callback_query
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                user = cur.fetchone()
        
        if not user: return await query.answer("❌ مستخدم غير موجود")

        status_txt = "نشط ✅" if user['is_activated'] else "غير مفعل ❌"
        expiry = user['expiry_date'].strftime('%Y-%m-%d') if user['expiry_date'] else "غير محدد"
        
        text = (f"👤 <b>إدارة المستخدم:</b> <code>{user_id}</code>\n\n"
                f"• الحالة: {status_txt}\n"
                f"• ينتهي في: <code>{expiry}</code>\n"
                f"• الرمز السري: <code>{user['secret_token']}</code>")
        
        kb = [
            [InlineKeyboardButton("✅ تفعيل 30 يوم", callback_data=f"adm_act_{user_id}"),
             InlineKeyboardButton("🚫 تعطيل", callback_data=f"adm_deact_{user_id}")],
            [InlineKeyboardButton("🗑️ حذف نهائي", callback_data=f"adm_del_{user_id}")],
            [InlineKeyboardButton("🔙 عودة", callback_data='admin_users')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e: 
        logging.error(e)

async def update_user_status(update: Update, action: str, user_id: str):
    query = update.callback_query
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                if action == 'activate':
                    new_expiry = datetime.datetime.now() + datetime.timedelta(days=30)
                    cur.execute("UPDATE users SET is_activated = True, expiry_date = %s WHERE user_id = %s", (new_expiry, user_id))
                    msg = "✅ تم التفعيل"
                elif action == 'deactivate':
                    cur.execute("UPDATE users SET is_activated = False WHERE user_id = %s", (user_id,))
                    msg = "❌ تم التعطيل"
                elif action == 'delete':
                    cur.execute("DELETE FROM entities WHERE user_id = %s", (user_id,))
                    cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
                    msg = "🗑️ تم الحذف"
                conn.commit()
        await query.answer(msg, show_alert=True)
        await list_users(update)
    except Exception as e: 
        logging.error(e)

# --- 4. الإحصائيات ---
async def show_admin_stats(update: Update):
    query = update.callback_query
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM users WHERE is_activated = True")
            active = cur.fetchone()[0]
    
    text = f"📊 <b>إحصائيات نظام Mr.MHO:</b>\n\n• إجمالي المستخدمين: {total}\n• المشتركين النشطين: {active}"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]]), parse_mode=ParseMode.HTML)
