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
    # نستخدم الكيبورد من ملف keyboards لتوحيد التصميم
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
    # توليد كود يبدأ بـ MHO كما تحب
    new_code = f"MHO-{secrets.token_hex(4).upper()}"
    
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # تعديل اسم الجدول إلى activation_codes واسم الأعمدة لتطابق نظامك
                cur.execute(
                    "INSERT INTO activation_codes (code, days_valid) VALUES (%s, %s)",
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
        await query.answer("❌ خطأ: تأكد من وجود جدول activation_codes")

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

# بقية الدوال (manage_single_user, update_user_status, show_admin_stats) تبقى كما هي لديك
