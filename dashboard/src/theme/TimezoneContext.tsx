import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  formatDateTime,
  formatTime,
  loadStoredTimezone,
  TIMEZONE_STORAGE_KEY,
  timezoneLabel,
  type AppTimezone,
} from "../lib/timezone";

interface TimezoneContextValue {
  timezone: AppTimezone;
  timezoneName: string;
  setTimezone: (tz: AppTimezone) => void;
  formatDateTime: (iso: string | null | undefined) => string;
  formatTime: (iso: string) => string;
}

const TimezoneContext = createContext<TimezoneContextValue | null>(null);

export function TimezoneProvider({ children }: { children: ReactNode }) {
  const [timezone, setTimezoneState] = useState<AppTimezone>(() => loadStoredTimezone());

  const setTimezone = useCallback((next: AppTimezone) => {
    setTimezoneState(next);
    localStorage.setItem(TIMEZONE_STORAGE_KEY, next);
  }, []);

  const value = useMemo(
    () => ({
      timezone,
      timezoneName: timezoneLabel(timezone),
      setTimezone,
      formatDateTime: (iso: string | null | undefined) => formatDateTime(iso, timezone),
      formatTime: (iso: string) => formatTime(iso, timezone),
    }),
    [timezone, setTimezone],
  );

  return <TimezoneContext.Provider value={value}>{children}</TimezoneContext.Provider>;
}

export function useTimezone(): TimezoneContextValue {
  const ctx = useContext(TimezoneContext);
  if (!ctx) {
    throw new Error("useTimezone must be used within TimezoneProvider");
  }
  return ctx;
}
