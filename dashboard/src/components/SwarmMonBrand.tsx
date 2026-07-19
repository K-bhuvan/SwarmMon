import { Link } from "react-router-dom";

/** SwarmMon mark — monitoring sweep + healthy fleet nodes. */
export function SwarmMonLogo({ size = 36 }: { size?: number }) {
  return (
    <img
      className="brand-logo-svg"
      width={size}
      height={size}
      src="/logo.svg"
      alt=""
      aria-hidden="true"
    />
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
