import React, { useState } from 'react';

const SettingsForm = () => {
  return (
    <div className="p-4 space-y-6 dir-rtl" dir="rtl">
      {/* قسم المدخلات */}
      <div className="space-y-4">
        <div className="flex justify-between items-center text-sm">
          <span className="flex items-center gap-2">تفعيل فلتر الموجة السابقة <i className="fa-solid fa-circle-info text-gray-600 text-[10px]"></i></span>
          <input type="checkbox" className="w-4 h-4 accent-[#deff9a]" defaultChecked />
        </div>

        <div className="flex justify-between items-center">
          <span className="text-sm">مستوى الفيبوناتشي %</span>
          <input type="number" defaultValue="50" className="bg-[#1a1a1a] border border-gray-800 text-center w-16 py-1 rounded text-[#deff9a]" />
        </div>

        <div className="flex justify-between items-center text-sm">
          <span>قاعدة 1: سحب السيولة</span>
          <input type="checkbox" className="w-4 h-4 accent-[#deff9a]" defaultChecked />
        </div>

        <div className="flex justify-between items-center text-sm">
          <span>قاعدة 2: الفجوة السعرية (FVG) : الطول</span>
          <div className="flex gap-2">
             <input type="number" defaultValue="10" className="bg-[#1a1a1a] border border-gray-800 text-center w-12 py-1 rounded" />
             <input type="checkbox" className="w-4 h-4 accent-[#deff9a]" defaultChecked />
          </div>
        </div>
      </div>

      {/* قسم إعدادات التداول */}
      <div className="pt-4 border-t border-gray-900">
        <h3 className="text-[#deff9a] text-[10px] mb-4 flex items-center gap-2 uppercase tracking-widest">
           <span className="w-2 h-2 bg-green-500 rounded-full"></span> إعدادات التداول
        </h3>
        
        <div className="grid grid-cols-1 gap-4">
          <div className="flex justify-between items-center">
            <span className="text-xs text-gray-400">عدد الإشارات لكل مستوى</span>
            <input type="number" defaultValue="2" className="bg-[#1a1a1a] border border-gray-800 text-center w-12 py-1 rounded" />
          </div>
          <div className="flex justify-between items-center">
            <span className="text-xs text-gray-400">عدد الأيام بين الإشارات لكل مستوى</span>
            <input type="number" defaultValue="1" className="bg-[#1a1a1a] border border-gray-800 text-center w-12 py-1 rounded" />
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsForm;
