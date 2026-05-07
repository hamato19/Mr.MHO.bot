# keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

def get_language_keyboard():
    """قائمة اختيار اللغة عند بداية التشغيل"""
    keyboard = [
        [
            InlineKeyboardButton("🇸🇦 العربية", callback_data='set_lang_ar'), 
            InlineKeyboardButton("🇺🇸 English", callback_data='set_lang_en')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_main_menu(uid, bot_username="bot"):
    """القائمة الرئيسية للبوت"""
    kb = [
        [
            InlineKeyboardButton("👤 حسابي", callback_data='acc'), 
            InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data='renew_sub')
        ],
        [
            InlineKeyboardButton("📢 ربط قناة", callback_data='add_ch'),
            InlineKeyboardButton("📺 قنواتي", callback_data='view_chs')
        ],
        [
            InlineKeyboardButton("🌐 روابط الويب هوك", callback_data='view_wh'), 
            InlineKeyboardButton("🔄 تحديث الرمز", callback_data='gen_token')
        ],
        [
            InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{bot_username}?startchannel=true")
        ],
        [
            InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)
        ]
    ]
    
    # إضافة زر لوحة التحكم للأدمن فقط
    if int(uid) == config.ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 لوحة التحكم (الأدمن)", callback_data='admin_panel')])
        
    return InlineKeyboardMarkup(kb)

def get_channel_request_keyboard():
    """زر طلب مشاركة القناة (Reply Keyboard)"""
    kb = [
        [
            KeyboardButton(
                "📢 اختر القناة", 
                request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True)
            )
        ]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)

def get_back_to_home():
    """زر العودة للقائمة الرئيسية"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للقائمة الرئيسية", callback_data='home')]])

def get_admin_main_keyboard():
    """لوحة تحكم الأدمن الخاصة"""
    kb = [
        [InlineKeyboardButton("👥 قائمة المستخدمين", callback_data='admin_users')],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data='admin_stats')],
        [InlineKeyboardButton("🔑 توليد أكواد", callback_data='admin_generate_code')],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='home')]
    ]
    return InlineKeyboardMarkup(kb)

def get_code_generation_keyboard():
    """أزرار اختيار مدة الكود المراد توليده للأدمن (تم إصلاحها)"""
    kb = [
        [InlineKeyboardButton("🎁 تجريبي (5 أيام)", callback_data='gen_days_5')],
        [InlineKeyboardButton("📅 شهر (30 يوم)", callback_data='gen_days_30')],
        [InlineKeyboardButton("📅 3 أشهر (90 يوم)", callback_data='gen_days_90')],
        [InlineKeyboardButton("📅 سنة (365 يوم)", callback_data='gen_days_365')],
        [InlineKeyboardButton("🔙 عودة للوحة الأدمن", callback_data='admin_panel')]
    ]
    return InlineKeyboardMarkup(kb)

def get_entities_keyboard(entities):
    """زر قنواتي: عرض القنوات مع معالجة خطأ البيانات والمسافات"""
    keyboard = []
    
    for ent in entities:
        try:
            # التأكد من استخراج المعرف والاسم بشكل صحيح
            if isinstance(ent, (tuple, list)) and len(ent) >= 2:
                ent_id = ent[0]
                ent_name = ent[1]
            else:
                ent_id = ent
                ent_name = "قناة/مجموعة"

            keyboard.append([InlineKeyboardButton(f"❌ {ent_name}", callback_data=f"del_ent_{ent_id}")])
        except Exception as e:
            print(f"Error processing entity: {e}")
            continue
    
    keyboard.append([InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')])
    return InlineKeyboardMarkup(keyboard)

def get_renewal_keyboard():
    """واجهة تجديد الاشتراك"""
    kb = [
        [InlineKeyboardButton("📥 إدخال كود التفعيل", callback_data='renew_sub')],
        [InlineKeyboardButton("💳 طلب كود / الدعم الفني", url=config.SUPPORT_LINK)],
        [InlineKeyboardButton("🏠 عودة", callback_data='home')]
    ]
    return InlineKeyboardMarkup(kb)
