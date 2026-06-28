import { useEffect, useState } from "react";
import { TIMEZONE_OPTIONS } from "../lib/timezone";
import { loadDisplayName, saveDisplayName } from "../lib/userPreferences";
import { useTheme } from "../theme/ThemeContext";
import type { Theme } from "../theme/theme";
import { useTimezone } from "../theme/TimezoneContext";
import type { AppTimezone } from "../lib/timezone";

const THEME_OPTIONS: { value: Theme; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark (VS Code)" },
  { value: "system", label: "Match system" },
];

export function DisplayPreferences() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { timezone, timezoneName, setTimezone, formatDateTime } = useTimezone();
  const [displayName, setDisplayName] = useState(loadDisplayName);
  const [previewTick, setPreviewTick] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setPreviewTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  function handleNameChange(value: string) {
    setDisplayName(value);
    saveDisplayName(value);
  }

  const previewIso = new Date(previewTick).toISOString();

  return (
    <div className="settings-fields">
      {displayName && (
        <p className="settings-page-sub">
          Viewing as <strong>{displayName}</strong>
        </p>
      )}
      <label className="settings-field">
        <span className="settings-field-label">Display name</span>
        <span className="settings-field-hint">Optional — shown in this browser only (no login yet).</span>
        <input
          type="text"
          placeholder="Mike"
          value={displayName}
          onChange={(e) => handleNameChange(e.target.value)}
          autoComplete="name"
        />
      </label>

      <label className="settings-field">
        <span className="settings-field-label">Theme</span>
        <span className="settings-field-hint">
          Active appearance: <strong>{resolvedTheme}</strong>
        </span>
        <select
          value={theme}
          onChange={(e) => setTheme(e.target.value as Theme)}
          aria-label="Color theme"
        >
          {THEME_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>

      <label className="settings-field">
        <span className="settings-field-label">Time zone</span>
        <span className="settings-field-hint">
          Fleet and incident timestamps use this zone. Backend stays UTC.
        </span>
        <select
          value={timezone}
          onChange={(e) => setTimezone(e.target.value as AppTimezone)}
          aria-label="Display time zone"
        >
          {TIMEZONE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>

      <p className="settings-preview">
        Preview ({timezoneName}): <time>{formatDateTime(previewIso)}</time>
      </p>
    </div>
  );
}
