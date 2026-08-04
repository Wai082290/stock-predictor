'use client';

import Image from 'next/image';

// 純圖標 LOGO
export function Logo({ size = 40 }: { size?: number }) {
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl blur-md opacity-40 animate-pulse"></div>
      <div className="relative rounded-xl overflow-hidden shadow-lg" style={{ width: size, height: size }}>
        <Image
          src="/logo.png"
          alt="Logo"
          width={size}
          height={size}
          className="w-full h-full object-cover"
          priority
        />
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
        <h1 className={`${s.title} font-black leading-none text-gradient`}>
          PAPAYA STOCK
        </h1>
        <p className={`${s.subtitle} text-slate-500 tracking-widest mt-0.5`}>
          PAPAYA PREDICTION SYSTEM
        </p>
      </div>
    </div>
  );
}