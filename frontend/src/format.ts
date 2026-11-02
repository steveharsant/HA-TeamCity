const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
  ["second", 1],
];

export function relativeTime(iso: string, language: string, now = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000);
  const format = new Intl.RelativeTimeFormat(language, { numeric: "auto" });
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size || unit === "second") {
      return format.format(Math.round(seconds / size), unit);
    }
  }
  return format.format(0, "second");
}

export function duration(startIso: string | null, endIso: string | null): string | null {
  if (!startIso || !endIso) {
    return null;
  }
  const total = Math.max(
    0,
    Math.round((new Date(endIso).getTime() - new Date(startIso).getTime()) / 1000),
  );
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours) {
    return `${String(hours)}h ${String(minutes)}m`;
  }
  if (minutes) {
    return `${String(minutes)}m ${String(seconds)}s`;
  }
  return `${String(seconds)}s`;
}

export function buildLabel(number: string | null, id: number): string {
  return number ? `#${number}` : `id ${String(id)}`;
}
