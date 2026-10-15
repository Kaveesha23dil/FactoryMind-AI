export type Preferences = {
  appearance: "light" | "dark" | "system";
  density: "comfortable" | "compact";
  dateFormat: "medium" | "iso" | "day-first";
  timeFormat: "12h" | "24h";
  timeZone: string;
};
export const PREFERENCE_KEY = "factorymind.preferences.v1";
export const PREFERENCE_EVENT = "factorymind:preferences";
export const DEFAULT_PREFERENCES: Preferences = { appearance: "light", density: "comfortable", dateFormat: "medium", timeFormat: "12h", timeZone: "system" };
export function validatePreferences(value: unknown): value is Preferences {
  if (!value || typeof value !== "object") return false;
  const p = value as Preferences;
  if (!Object.keys(DEFAULT_PREFERENCES).every(key => Object.hasOwn(p, key)) || Object.keys(p).length !== 5) return false;
  if (!["light", "dark", "system"].includes(p.appearance) || !["comfortable", "compact"].includes(p.density) || !["medium", "iso", "day-first"].includes(p.dateFormat) || !["12h", "24h"].includes(p.timeFormat) || typeof p.timeZone !== "string") return false;
  try { if (p.timeZone !== "system") new Intl.DateTimeFormat("en", { timeZone: p.timeZone }); } catch { return false; }
  return p.timeZone.length > 0;
}
export function readPreferences(): Preferences {
  try {
    if (typeof window === "undefined") return { ...DEFAULT_PREFERENCES };
    const value: unknown = JSON.parse(localStorage.getItem(PREFERENCE_KEY) ?? "null");
    return validatePreferences(value) ? value : { ...DEFAULT_PREFERENCES };
  } catch { return { ...DEFAULT_PREFERENCES }; }
}
export function savePreferences(value: Preferences): void {
  if (!validatePreferences(value)) throw new Error("Choose valid preferences and an IANA timezone, such as Asia/Colombo.");
  const serialized = JSON.stringify(value);
  localStorage.setItem(PREFERENCE_KEY, serialized);
  if (localStorage.getItem(PREFERENCE_KEY) !== serialized) throw new Error("The browser did not persist these preferences.");
  window.dispatchEvent(new Event(PREFERENCE_EVENT));
}
export function formatTimestamp(iso: string, p: Preferences): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const options: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: p.timeFormat === "12h", ...(p.timeZone === "system" ? {} : { timeZone: p.timeZone }) };
  if (p.dateFormat === "medium") return new Intl.DateTimeFormat("en-US", { ...options, dateStyle: undefined, year: "numeric", month: "short", day: "numeric" }).format(date);
  const parts = new Intl.DateTimeFormat("en-GB", { ...options, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(date);
  const get = (type: string) => parts.find(part => part.type === type)?.value ?? "";
  const day = p.dateFormat === "iso" ? `${get("year")}-${get("month")}-${get("day")}` : `${get("day")}/${get("month")}/${get("year")}`;
  return `${day}, ${new Intl.DateTimeFormat("en-US", options).format(date)}`;
}
