const inr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});
const compact = new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 });
const dateFmt = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("en-IN", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return inr.format(Number(value));
}

export function moneyCompact(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return `₹${compact.format(Number(value))}`;
}

export function date(value: string | null | undefined): string {
  if (!value) return "—";
  // A bare YYYY-MM-DD is a calendar date; parse it as local midnight so it never shifts a day.
  return dateFmt.format(new Date(value.length === 10 ? `${value}T00:00:00` : value));
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return dateTimeFmt.format(new Date(value));
}

export function label(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}
