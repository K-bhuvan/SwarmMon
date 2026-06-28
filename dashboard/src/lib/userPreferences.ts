export const USER_DISPLAY_NAME_KEY = "swarmmon-user-display-name";

export function loadDisplayName(): string {
  try {
    return localStorage.getItem(USER_DISPLAY_NAME_KEY)?.trim() ?? "";
  } catch {
    return "";
  }
}

export function saveDisplayName(name: string): void {
  const trimmed = name.trim();
  try {
    if (trimmed) {
      localStorage.setItem(USER_DISPLAY_NAME_KEY, trimmed);
    } else {
      localStorage.removeItem(USER_DISPLAY_NAME_KEY);
    }
  } catch {
    /* ignore */
  }
}
