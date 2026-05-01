import React from 'react';

const Header = () => {
  return (
    <div className="flex flex-col items-center mb-8 border-b border-gray-900 pb-4">
      <h1 className="text-xl font-bold text-white tracking-tighter">
        ARAM <span className="text-[#deff9a]">HEATMAP</span> 🔥
      </h1>
      <div className="flex items-center gap-2 mt-1">
        <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
        <span className="text-[10px] text-gray-500 uppercase tracking-widest">System Online</span>
      </div>
    </div>
  );
};

export default Header;
