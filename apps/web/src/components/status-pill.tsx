import { cn } from "@/lib/utils";

export function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium",
        ok ? "bg-good/15 text-good" : "bg-bad/15 text-bad",
      )}
    >
      <span aria-hidden className={cn("size-2 rounded-full", ok ? "bg-good" : "bg-bad")} />
      {label}
    </span>
  );
}
