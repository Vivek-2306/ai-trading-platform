import { AutoRefresh } from "@/components/auto-refresh";
import { StatusPill } from "@/components/status-pill";
import { Card, CardTitle } from "@/components/ui/card";
import { getSystemStatus } from "@/lib/api";

export const dynamic = "force-dynamic";

const NAMES: Record<string, string> = { database: "Database", redis: "Redis" };

export default async function Status() {
  const status = await getSystemStatus();
  const services: { name: string; ok: boolean; note: string }[] =
    status.api === "down"
      ? [{ name: "API", ok: false, note: "Not reachable" }]
      : [
          { name: "API", ok: true, note: `v${status.version} · ${status.environment}` },
          ...Object.entries(status.checks).map(([key, value]) => ({
            name: NAMES[key] ?? key,
            ok: value === "ok",
            note: value === "ok" ? "Connected" : "Unavailable",
          })),
        ];

  return (
    <div className="space-y-6">
      <AutoRefresh />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">System status</h1>
        <p className="mt-1 text-muted">Updates every 10 seconds.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {services.map((service) => (
          <Card key={service.name}>
            <CardTitle>{service.name}</CardTitle>
            <div className="mt-3">
              <StatusPill ok={service.ok} label={service.ok ? "Operational" : "Down"} />
            </div>
            <p className="mt-3 text-sm text-muted">{service.note}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
