// Formatting helpers — Arabic-Indic numerals, Hijri-safe Gregorian dates,
// relative time, percentages and compact counts.

const dateFmt = new Intl.DateTimeFormat("ar-EG", {
  year: "numeric",
  month: "long",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: true,
  timeZone: "UTC",
});

const dateShortFmt = new Intl.DateTimeFormat("ar-EG", {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: true,
  timeZone: "UTC",
});

const numFmt = new Intl.NumberFormat("ar-EG");
const compactFmt = new Intl.NumberFormat("ar-EG", { notation: "compact", maximumFractionDigits: 1 });

export function formatNumber(n: number): string {
  return numFmt.format(n);
}

export function formatCompact(n: number): string {
  return compactFmt.format(n);
}

export function formatPercent(n: number): string {
  return numFmt.format(Math.round(n * 100));
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return dateFmt.format(d);
}

export function formatShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return dateShortFmt.format(d);
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return "";
  const diffSec = Math.round((Date.now() - d) / 1000);
  const abs = Math.abs(diffSec);
  const rtf = new Intl.RelativeTimeFormat("ar", { numeric: "auto" });
  if (abs < 60) return rtf.format(diffSec, "second");
  if (abs < 3600) return rtf.format(Math.round(diffSec / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diffSec / 3600), "hour");
  if (abs < 2592000) return rtf.format(Math.round(diffSec / 86400), "day");
  return formatShort(iso);
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0] ? parts[0][0] : "";
  const second = parts.length > 1 && parts[1] ? parts[1][0] : "";
  return (first + second).toUpperCase();
}

export function pluralAr(n: number, one: string, two: string, many: string): string {
  const abs = Math.abs(n);
  if (abs === 1) return `${formatNumber(n)} ${one}`;
  if (abs === 2) return `${formatNumber(n)} ${two}`;
  if (abs >= 3 && abs <= 10) return `${formatNumber(n)} ${many}`;
  return `${formatNumber(n)} ${many}`;
}
