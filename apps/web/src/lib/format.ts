/** Small display helpers for numbers that may be missing. Never throws. */

export const pct = (value: number | null | undefined, digits = 1): string =>
  value === null || value === undefined || !Number.isFinite(value)
    ? "n/a"
    : `${value.toFixed(digits)}%`;

export const num = (value: number | null | undefined, digits = 2): string =>
  value === null || value === undefined || !Number.isFinite(value) ? "n/a" : value.toFixed(digits);

/** An exact decimal string with thousands separators and no float rounding. */
export function money(value: string | null | undefined, maxDecimals = 2): string {
  if (value === null || value === undefined || value === "") return "n/a";
  const [whole = "", fraction = ""] = value.split(".");
  const sign = whole.startsWith("-") ? "-" : "";
  const digits = whole.replace("-", "").replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const trimmed = fraction.slice(0, maxDecimals).replace(/0+$/, "");
  const body = `${digits}${trimmed ? `.${trimmed}` : ""}`;
  return body === "0" ? "0" : `${sign}${body}`; // never "-0"
}

export const SEGMENT_LABEL: Record<string, string> = {
  tuning: "Tuning region",
  walk_forward: "Walk-forward",
  oos: "Locked out-of-sample",
};

export const day = (iso: string): string => iso.slice(0, 10);
