import logging
import config
from telegram import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButtonRequestChat
)

logger = logging.getLogger(__name__)

# --- 1. واجهة الخصوصية ---
def get_disclaimer_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 سياسة الخصوصية", callback_data='view_priv')],
        [InlineKeyboardButton("✅ موافق ", callback_data='accept_tos')],
        [InlineKeyboardButton("❌ رفض", callback_data='reject_tos')]
    ])

# --- 2. واجهة التفعيل والتجديد ---
def get_subscription_options():
    kb = [
        [InlineKeyboardButton("💳 اشترك الآن", url="https://sumoualarqam.com/")],
        [InlineKeyboardButton("🎫 ارسل كود التفعيل", callback_data='how_to_act')],
        [InlineKeyboardButton("⬅️ رجوع", callback_data='home')]
    ]
    return InlineKeyboardMarkup(kb)

# --- 3. القائمة الرئيسية ---
async def get_main_menu(uid, bot_username="bot"):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data='ren')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📋 قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄 توليد رمز الأمان", callback_data='tok')],
        [InlineKeyboardButton("🤖 إضافة البوت مشرف", url=f"https://t.me/{bot_username}?startchannel=true&admin=post_messages+edit_messages+delete_messages")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    if str(uid) == str(config.ADMIN_ID):
        kb.append([InlineKeyboardButton("Admin panel", callback_data='adm')])
    return InlineKeyboardMarkup(kb)

# --- 4. لوحة الأدمن الرئيسية ---
def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 إدارة الاشتراكات", callback_data='adm_u'),
            InlineKeyboardButton("🎫 توليد أكواد", callback_data='adm_gen_menu')
        ],
        [
            InlineKeyboardButton("📢 إرسال تنبية للاعضاء", callback_data='broadcast_prompt'),
            InlineKeyboardButton("📊 الإحصائيات", callback_data='adm')
        ],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='home')]
    ])

# --- 5. التحكم بالمستخدم (من قبل الأدمن) ---
def get_user_control_keyboard(target_id, is_active):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تفعيل (اختر المدة)", callback_data=f"ask_act_{target_id}")],
        [InlineKeyboardButton("🗑️ حذف المستخدم", callback_data=f"del_u_{target_id}")],
        [InlineKeyboardButton("🔙 عودة للقائمة", callback_data='adm_u')]
    ])

def get_activation_periods_keyboard(target_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("10 أيام", callback_data=f"act_10_{target_id}"),
            InlineKeyboardButton("30 يوم", callback_data=f"act_30_{target_id}")
        ],
        [
            InlineKeyboardButton("60 يوم", callback_data=f"act_60_{target_id}"),
            InlineKeyboardButton("90 يوم", callback_data=f"act_90_{target_id}")
        ],
        [InlineKeyboardButton("🔙 إلغاء", callback_data=f"user_info_{target_id}")]
    ])

# --- 6. إدارة قائمة المستخدمين ---
def get_users_management_keyboard(users):
    keyboard = []
    if users:
        for user in users:
            uid = user['user_id']
            status_icon = "✅" if user.get('is_activated') else "❌"
            keyboard.append([InlineKeyboardButton(f"{status_icon} ID: {uid}", callback_data=f"user_info_{uid}")])
    else:
        keyboard.append([InlineKeyboardButton("لا يوجد مستخدمين", callback_data="none")])
    
    keyboard.append([InlineKeyboardButton("🔙 لوحة التحكم", callback_data="adm")])
    return InlineKeyboardMarkup(keyboard)

# --- 7. إدارة القنوات ---
def get_entities_keyboard(entities):
    kb = []
    if not entities:
        kb.append([InlineKeyboardButton("❌ لا توجد قنوات مرتبطة", callback_data='none')])
    else:
        for ent in entities:
            try:
                if isinstance(ent, dict):
                    clean_id = str(ent.get('entity_id', '0')).strip()
                else:
                    clean_id = str(ent[1]).strip() 
                
                kb.append([
                    InlineKeyboardButton(f"🆔 {clean_id}", callback_data=f"view_{clean_id}"),
                    InlineKeyboardButton("🗑️ حذف", callback_data=f"del_ent_{clean_id}")
                ])
            except Exception as e:
                logger.error(f"Error rendering entity button: {e}")
                continue

    kb.append([InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data='add_channel')])
    kb.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='home')])
    return InlineKeyboardMarkup(kb)

# --- 8. توليد الأكواد ---
def get_generation_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("10 أيام", callback_data='gen_10'), InlineKeyboardButton("30 يوم", callback_data='gen_30')],
        [InlineKeyboardButton("60 يوم", callback_data='gen_60'), InlineKeyboardButton("90 يوم", callback_data='gen_90')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='adm')]
    ])

# --- 9. زر اختيار القناة المطور والديناميكي ---
def get_request_channel_keyboard(user_id=1):
    """هذه الدالة تظهر كيبورد أسفل الشاشة لاختيار قناة مع الحفاظ على آيدي طلب فريد"""
    req_id = int(str(user_id)[-7:]) if user_id != 1 else 1
    return ReplyKeyboardMarkup([
        [
            KeyboardButton(
                text="📢 اختر القناة التي تريد ربطها", 
                request_chat=KeyboardButtonRequestChat(
                    request_id=req_id, 
                    chat_is_channel=True
                )
            )
        ],
        [KeyboardButton(text="🔙 إلغاء والعودة للقائمة")]
    ], resize_keyboard=True, one_time_keyboard=True)


# --- دوال مساعدة وتحكم خارجي ---
def get_back_home():
    """زر موحد للعودة للقائمة الرئيسية في أي وقت"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 العودة للقائمة", callback_data='home')]])


async def process_add_channel_logic(query, context, uid, is_owner, user, database):
    """دالة مستقلة لمعالجة ربط القنوات معزولة داخل موديول الكيبورد لحل مشاكل السيرفر نهائياً"""
    # السماح للأدمن دائماً، أو للمشترك النشط
    if is_owner or (user and user.get('is_activated')):
        
        # فحص إضافي للمشترك العادي لمنعه من طلب زر التفويض إذا كان يملك قناة فعلاً
        if not is_owner:
            ents = database.get_user_entities(uid)
            if ents and len(ents) >= 1:
                await query.answer("⚠️ عذراً، يمكنك إضافة قناة واحدة فقط كحد أقصى!", show_alert=True)
                return

        # 1. استجابة سريعة للزر لتفادي الساعة الرملية المعلقة
        try:
            await query.answer()
        except:
            pass

        # 2. تعديل نص الرسالة الحالية لتوجيه المستخدم للنظر بالأسفل
        try:
            await query.edit_message_text(
                text="⏳ <b>جاري فتح معالج الربط...</b>\n\nالرجاء النظر إلى أسفل الشاشة واستخدام الكيبورد المظهر هناك لاختيار قناتك وتفويض البوت.",
                parse_mode='HTML'
            )
        except:
            pass

        # 3. إرسال الكيبورد الخاص بطلب تفويض القناة وتمرير الـ uid كمعرف فريد
        await context.bot.send_message(
            chat_id=uid,
            text="📢 <b>نظام ربط وتفويض القنوات المطور:</b>\n\nاضغط على الزر الأزرق الكبير بالأسفل واقرن قناتك ببوت الإشارات مباشرة.",
            parse_mode='HTML',
            reply_markup=get_request_channel_keyboard(uid)
        )
    else:
        await query.answer("⚠️ عذراً، هذه الميزة للمشتركين فقط.", show_alert=True)
