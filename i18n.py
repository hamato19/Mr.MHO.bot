# قاموس النصوص الموحد للبوت
STRINGS = {
    'ar': {
        'welcome': "🚀 مرحباً بك {name} في نظام سمو الأرقام",
        'main_menu': "🌟 <b>لوحة تحكم النظام تعمل بكفاءة:</b>",
        'acc_info': (
            "👤 <b>بيانات الحساب:</b>\n\n"
            "• الحالة: {status}\n"
            "• المتبقي: {expiry}\n"
            "• الرمز: <code>{token}</code>"
        ),
        'buy_code': "💳 شراء كود تفعيل",
        'wait_code': "⚠️ <b>الوصول مقيد.</b>\nيرجى إرسال كود التفعيل للبدء:",
        'expired': "❌ <b>انتهى اشتراكك!</b>\nيرجى إرسال كود جديد للتجديد:",
        'invalid_code': "❌ الكود خاطئ أو مستخدم مسبقاً.",
        'success_act': "✅ تم التفعيل بنجاح لمدة {days} يوم!",
        'spam_alert': "⛔️ <b>عملية محظورة:</b> لقد تجاوزت حد الطلبات المسموح به.",
        'banned_msg': "🚫 <b>وصول محظور:</b> حسابك محظور نهائياً من النظام.",
        'db_error': "❌ عذراً، هناك مشكلة في الاتصال بقاعدة البيانات حالياً.",
        'home_btn': "🏠 القائمة الرئيسية",
        'back_btn': "🔙 عودة",
        'admin_panel': "👮 لوحة تحكم الإدارة العليا",
    },
    'en': {
        'welcome': "🚀 Welcome {name} to Sumou Al-Arqam System",
        'main_menu': "🌟 <b>System Dashboard is active:</b>",
        'acc_info': (
            "👤 <b>Account Details:</b>\n\n"
            "• Status: {status}\n"
            "• Remaining: {expiry}\n"
            "• Token: <code>{token}</code>"
        ),
        'buy_code': "💳 Purchase Activation Code",
        'wait_code': "⚠️ <b>Access Restricted.</b>\nPlease send your activation code:",
        'expired': "❌ <b>Subscription Expired!</b>\nPlease send a new code:",
        'invalid_code': "❌ Invalid or already used code.",
        'success_act': "✅ Activation successful for {days} days!",
        'spam_alert': "⛔️ <b>Action Blocked:</b> Rate limit exceeded.",
        'banned_msg': "🚫 <b>Access Denied:</b> Your account is permanently banned.",
        'db_error': "❌ Sorry, database connection error.",
        'home_btn': "🏠 Main Menu",
        'back_btn': "🔙 Back",
        'admin_panel': "👮 Admin Control Panel",
    }
}

def get_text(key, lang='ar', **kwargs):
    """دالة جلب النص بناءً على مفتاح اللغة"""
    try:
        text = STRINGS.get(lang, STRINGS['ar']).get(key, f"Missing Key: {key}")
        return text.format(**kwargs) if kwargs else text
    except Exception as e:
        return f"Error text: {key}"
