/** Backend sends UTC; naive ISO strings (no Z) are treated as UTC. */
export function parseApiTimestamp(iso: string): number {
  const normalized =
    iso.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`;
  return new Date(normalized).getTime();
}

export const TIMEZONE_STORAGE_KEY = "swarmmon-timezone";

export type AppTimezone =
  | "America/New_York"
  | "America/Chicago"
  | "America/Denver"
  | "America/Phoenix"
  | "America/Los_Angeles"
  | "America/Anchorage"
  | "Pacific/Honolulu"
  | "UTC";

export const TIMEZONE_OPTIONS: { value: AppTimezone; label: string }[] = [
  { value: "America/New_York", label: "Eastern (ET)" },
  { value: "America/Chicago", label: "Central (CT)" },
  { value: "America/Denver", label: "Mountain (MT)" },
  { value: "America/Phoenix", label: "Arizona (MST)" },
  { value: "America/Los_Angeles", label: "Pacific (PT)" },
  { value: "America/Anchorage", label: "Alaska (AKT)" },
  { value: "Pacific/Honolulu", label: "Hawaii (HT)" },
  { value: "UTC", label: "UTC" },
];

const VALID_TIMEZONES = new Set<string>(TIMEZONE_OPTIONS.map((o) => o.value));

export function loadStoredTimezone(): AppTimezone {
  try {
    const stored = localStorage.getItem(TIMEZONE_STORAGE_KEY);
    if (stored && VALID_TIMEZONES.has(stored)) {
      return stored as AppTimezone;
    }
  } catch {
    /* ignore */
  }
  return "America/New_York";
}

export function timezoneLabel(tz: AppTimezone): string {
  return TIMEZONE_OPTIONS.find((o) => o.value === tz)?.label ?? tz;
}

/** Full date + time in the selected zone (e.g. Jun 27, 2026, 1:36 PM EDT). */
export function formatDateTime(
  iso: string | null | undefined,
  timeZone: AppTimezone,
): string {
  if (!iso) return "—";
  const ms = parseApiTimestamp(iso);
  if (Number.isNaN(ms)) return iso;
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(ms);
}

/** Time only in the selected zone (e.g. 1:36:28 PM EDT). */
export function formatTime(iso: string, timeZone: AppTimezone): string {
  const ms = parseApiTimestamp(iso);
  if (Number.isNaN(ms)) return iso;
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  }).format(ms);
}
