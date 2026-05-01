import React from 'react';

const Header = () => (
  <div className="flex flex-col items-center justify-center space-y-2">
    <div className="w-16 h-16 bg-[#deff9a] rounded-2xl flex items-center justify-center rotate-3 shadow-lg shadow-[#deff9a]/10">
      <span className="text-3xl font-black text-black -rotate-3">M</span>
    </div>
    <h1 className="text-2xl font-black tracking-tight mt-2">
      ARAM <span className="text-[#deff9a]">HEATMAP</span>
    </h1>
    <div className="px-3 py-1 bg-green-500/10 border border-green-500/20 rounded-full flex items-center gap-2">
      <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></div>
      <span className="text-[10px] text-green-500 font-bold uppercase tracking-tighter">Live System</span>
    </div>
  </div>
);

export default Header;
