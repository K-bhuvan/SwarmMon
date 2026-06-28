import { NavLink } from "react-router-dom";

export function SettingsGearLink() {
  return (
    <NavLink
      to="/settings"
      className={({ isActive }) =>
        `settings-gear-link${isActive ? " settings-gear-link-active" : ""}`
      }
      aria-label="Settings"
      title="Settings"
    >
      <svg
        className="settings-gear-icon"
        viewBox="0 0 24 24"
        width={22}
        height={22}
        aria-hidden
        focusable="false"
      >
        <path
          fill="currentColor"
          d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm8.94-3.5a7.96 7.96 0 0 0-.12-1l2.03-1.58a.75.75 0 0 0 .18-.97l-1.92-3.32a.75.75 0 0 0-.91-.33l-2.39.96a8.14 8.14 0 0 0-1.73-1l-.36-2.54a.75.75 0 0 0-.74-.64h-3.84a.75.75 0 0 0-.74.64l-.36 2.54c-.62.24-1.2.57-1.73 1l-2.39-.96a.75.75 0 0 0-.91.33L2.95 8.95a.75.75 0 0 0 .18.97L5.16 12.4a7.96 7.96 0 0 0 0 2l-2.03 1.58a.75.75 0 0 0-.18.97l1.92 3.32c.2.35.6.48.91.33l2.39-.96c.53.43 1.11.76 1.73 1l.36 2.54c.08.36.38.62.74.62h3.84c.36 0 .66-.26.74-.62l.36-2.54c.62-.24 1.2-.57 1.73-1l2.39.96c.31.15.71.02.91-.33l1.92-3.32a.75.75 0 0 0-.18-.97L20.82 14.4c.08-.33.12-.66.12-1Z"
        />
      </svg>
    </NavLink>
  );
}
