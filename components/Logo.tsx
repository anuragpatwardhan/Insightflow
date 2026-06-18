export function LogoMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      <defs>
        <linearGradient id="if-bg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#0e1218" />
          <stop offset="100%" stopColor="#1a2230" />
        </linearGradient>
        <linearGradient id="if-stroke" x1="0" y1="32" x2="32" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#7aa2ff" />
          <stop offset="100%" stopColor="#5cd9a3" />
        </linearGradient>
        <radialGradient id="if-glow" cx="24" cy="8" r="8" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#9cb8ff" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#9cb8ff" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* tile */}
      <rect x="0.5" y="0.5" width="31" height="31" rx="8" fill="url(#if-bg)" stroke="#2b3540" />

      {/* ascending flow line */}
      <path
        d="M5 22 C 10 22, 11 16, 15 16 C 19 16, 20 10, 24 8"
        stroke="url(#if-stroke)"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />

      {/* trailing tick marks (the “stream”) */}
      <circle cx="5" cy="22" r="1.4" fill="#7aa2ff" opacity="0.5" />
      <circle cx="10" cy="20" r="1.1" fill="#7aa2ff" opacity="0.7" />
      <circle cx="15" cy="16" r="1.4" fill="#9cb8ff" />

      {/* focal insight node */}
      <circle cx="24" cy="8" r="6" fill="url(#if-glow)" />
      <circle cx="24" cy="8" r="2.6" fill="#e7eef7" />
    </svg>
  );
}

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark size={size} />
      <span className="text-[15px] font-semibold tracking-tight text-text">
        Insight<span className="text-accent">Flow</span>
      </span>
    </div>
  );
}
