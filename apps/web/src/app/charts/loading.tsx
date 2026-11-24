import { Card } from "@/components/ui/card";

export default function Loading() {
  return (
    <div className="space-y-4" aria-busy="true">
      <div className="h-8 w-48 animate-pulse rounded-lg bg-foreground/10" />
      <Card>
        <div className="h-[55dvh] min-h-72 animate-pulse rounded-xl bg-foreground/5" />
      </Card>
    </div>
  );
}
