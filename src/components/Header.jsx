import React from 'react';

const Header = () => {
  return (
    <div className="flex flex-col items-center py-6 border-b border-gray-900">
      <h1 className="text-xl font-bold tracking-wider text-[#f5f5f5]">
        Aram Heatmap <span className="text-[#deff9a]">🔥 v1.0</span>
      </h1>
      <div className="flex items-center mt-2">
        <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse ml-2"></span>
        <span className="text-[10px] text-gray-400 uppercase tracking-widest">System Active</span>
      </div>
    </div>
  );
};

export default Header;
