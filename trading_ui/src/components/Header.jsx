import React from 'react';

const Header = () => {
  return (
    <div className="w-full flex flex-col items-center justify-center text-center py-4 border-b border-gray-900/50">
      
      {/* حاوية النص والأيقونة - نستخدم flex-row-reverse لضمان الترتيب العربي الصحيح */}
      <div className="flex flex-row-reverse items-center justify-center gap-3">
        {/* النص جهة اليمين */}
        <h1 className="text-2xl font-bold text-white tracking-tight">
          إعدادات التداول
        </h1>
        {/* الأيقونة جهة اليسار (أو بجانب النص مباشرة) */}
        <span className="text-2xl animate-bounce">🔥</span>
      </div>

      {/* خط توضيحي سفلي أنيق بجانب "System Online" */}
      <div className="flex items-center gap-2 mt-3 bg-black/50 border border-gray-800 px-4 py-1 rounded-full shadow-lg">
        <div className="w-2 h-2 bg-[#deff9a] rounded-full animate-pulse shadow-[0_0_8px_#deff9a]"></div>
        <span className="text-[10px] text-gray-500 uppercase tracking-[0.2em] font-medium">
          Aram System Active
        </span>
      </div>
      
    </div>
  );
};

export default Header;
