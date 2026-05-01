import React from 'react';

const Header = () => {
  return (
    <div className="w-full flex flex-col items-center border-b border-gray-900 pb-6 mb-4">
      {/* شعار عصري مع أيقونة النار */}
      <h1 className="text-3xl font-extrabold text-white tracking-tighter flex items-center gap-1.5">
        Mr. <span className="text-[#deff9a]">MOH</span> 
        <span className="text-xl">🔥</span>
      </h1>
      
      {/* حالة الاتصال بشكل نبضي جذاب */}
      <div className="flex items-center gap-2 mt-2 bg-[#0a0a0a] border border-gray-800 px-4 py-1.5 rounded-full shadow-inner">
        <div className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse shadow-lg shadow-green-900"></div>
        <span className="text-xs text-gray-400 font-medium uppercase tracking-widest">
          System Online
        </span>
      </div>
    </div>
  );
};

export default Header;
