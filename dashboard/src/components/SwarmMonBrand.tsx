import { Link } from "react-router-dom";

/** SwarmMon mark — fleet nodes + monitor ring */
export function SwarmMonLogo({ size = 36 }: { size?: number }) {
  return (
    <svg
      className="brand-logo-svg"
      width={size}
      height={size}
      viewBox="0 0 48 48"
      aria-hidden
      focusable="false"
    >
      <defs>
        <linearGradient id="swarmmon-logo-bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#14b8a6" />
          <stop offset="55%" stopColor="#0ea5e9" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>
        <linearGradient id="swarmmon-logo-ring" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#5eead4" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#7dd3fc" stopOpacity="0.5" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="44" height="44" rx="12" fill="url(#swarmmon-logo-bg)" />
      <circle
        cx="24"
        cy="24"
        r="14"
        fill="none"
        stroke="url(#swarmmon-logo-ring)"
        strokeWidth="2"
        strokeDasharray="4 3"
        opacity="0.95"
      />
      <circle cx="24" cy="14" r="3.2" fill="#ecfdf5" />
      <circle cx="15" cy="28" r="3" fill="#e0f2fe" />
      <circle cx="33" cy="28" r="3" fill="#e0e7ff" />
      <circle cx="24" cy="32" r="2.6" fill="#fef9c3" />
      <circle cx="24" cy="24" r="2" fill="#22c55e" opacity="0.95" />
    </svg>
  );
}

export function SwarmMonBrand() {
  return (
    <Link to="/" className="app-brand" title="SwarmMon home">
      <SwarmMonLogo />
      <span className="app-brand-text">
        <span className="app-brand-name">SwarmMon</span>
        <span className="app-brand-tagline">Fleet observability</span>
      </span>
    </Link>
  );
}
