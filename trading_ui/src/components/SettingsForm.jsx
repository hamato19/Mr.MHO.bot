import React from 'react';

const SettingsForm = () => {
  return (
    <div className="space-y-6 text-right" dir="rtl">
      {/* قسم الاستراتيجية */}
      <div className="bg-[#0a0a0a] border border-gray-900 p-4 rounded-xl space-y-4">
        <div className="flex justify-between items-center">
          <span className="text-sm">تفعيل فلتر الموجة السابقة</span>
          <input type="checkbox" className="accent-[#deff9a]" defaultChecked />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm">مستوى الفيبوناتشي %</span>
          <input type="number" defaultValue="50" className="bg-black border border-gray-800 text-center w-16 py-1 rounded text-[#deff9a]" />
        </div>

        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-400 text-xs">قاعدة 1: سحب السيولة</span>
          <input type="checkbox" className="accent-[#deff9a]" defaultChecked />
        </div>
      </div>

      {/* قسم إعدادات التداول */}
      <div className="space-y-4 px-2">
        <h3 className="text-[#deff9a] text-[10px] uppercase tracking-widest flex items-center gap-2">
          <span className="w-1.5 h-1.5 bg-[#deff9a] rounded-full"></span> إعدادات التداول
        </h3>
        
        <div className="flex justify-between items-center">
          <span className="text-xs">عدد الإشارات لكل مستوى</span>
          <input type="number" defaultValue="2" className="bg-[#0a0a0a] border border-gray-800 text-center w-12 py-1 rounded" />
        </div>

        <div className="flex justify-between items-center">
          <span className="text-xs">عدد الأيام بين الإشارات</span>
          <input type="number" defaultValue="1" className="bg-[#0a0a0a] border border-gray-800 text-center w-12 py-1 rounded" />
        </div>
      </div>

      {/* زر الحفظ النهائي */}
      <button className="w-full bg-[#deff9a] text-black font-bold py-3 rounded-xl shadow-lg shadow-[#deff9a]/10 active:scale-95 transition-transform mt-4">
        تفعيل التداول الآلي
      </button>
    </div>
  );
};

export default SettingsForm;
