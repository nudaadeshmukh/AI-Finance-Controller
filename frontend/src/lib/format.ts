// The ONE place paise become rupees on the frontend (master_specification.md
// §23.6, CLAUDE.md rule 1). Nothing else in src/ divides by 100 or writes a
// ₹ sign.

const INR = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** paise (int) -> "₹1,23,456.00" with Indian digit grouping. */
export function rupees(paise: number): string {
  const sign = paise < 0 ? "-" : "";
  return `${sign}₹${INR.format(Math.abs(paise) / 100)}`;
}

/** paise -> "1,23,456.00" (no symbol) for dense table columns. */
export function rupeesPlain(paise: number): string {
  const sign = paise < 0 ? "-" : "";
  return `${sign}${INR.format(Math.abs(paise) / 100)}`;
}

/** 0.9175 -> "91.75%" */
export function percent(fraction: number, digits = 2): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** epoch seconds -> "5 Sep 2026" ("data as of" label). */
export function asOfDate(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function ms(value: number): string {
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value} ms`;
}
