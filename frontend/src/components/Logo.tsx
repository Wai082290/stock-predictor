'use client';

export function Logo({ size = 40 }: { size?: number }) {
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl blur-md opacity-60 animate-pulse"></div>
      <div className="relative bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-xl p-2 shadow-lg">
        <svg viewBox="0 0 40 40" className="w-full h-full">
          {/* 上升趨勢線 */}
          <defs>
            <linearGradient id="chartGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="1" />
            </linearGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="1" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
          
          {/* K線圖 */}
          <rect x="5" y="20" width="4" height="12" fill="url(#chartGrad)" rx="1"/>
          <rect x="12" y="14" width="4" height="18" fill="url(#chartGrad)" rx="1" opacity="0.9"/>
          <rect x="19" y="10" width="4" height="22" fill="url(#chartGrad)" rx="1"/>
          <rect x="26" y="6" width="4" height="26" fill="url(#chartGrad)" rx="1" opacity="0.9"/>
          
          {/* 趨勢線 */}
          <path
            d="M 7 26 L 14 20 L 21 16 L 28 10 L 35 6"
            stroke="#ffffff"
            strokeWidth="2"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#glow)"
          />
          
          {/* 上升箭頭 */}
          <path
            d="M 32 6 L 36 6 L 36 10"
            stroke="#ffffff"
            strokeWidth="2"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </div>
  );
}

// 帶文字的 LOGO
export function LogoWithText({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizes = {
    sm: { icon: 32, title: 'text-lg', subtitle: 'text-[10px]' },
    md: { icon: 44, title: 'text-2xl', subtitle: 'text-xs' },
    lg: { icon: 60, title: 'text-4xl', subtitle: 'text-sm' },
  };
  const s = sizes[size];
  
  return (
    <div className="flex items-center gap-3">
      <Logo size={s.icon} />
      <div>
        <h1 className={`${s.title} font-black leading-none`}>
          <span className="text-gradient">STOCK</span>
          <span className="text-white">SIGHT</span>
        </h1>
        <p className={`${s.subtitle} text-slate-500 tracking-widest mt-0.5`}>
          AI PREDICTION SYSTEM
        </p>
      </div>
    </div>
  );
}