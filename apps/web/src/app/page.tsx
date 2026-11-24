import { Card, CardTitle } from "@/components/ui/card";

export default function Home() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Overview</h1>
        <p className="mt-1 text-muted">Signals, risk and portfolio will appear here.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {["Signals", "Risk", "Portfolio"].map((name) => (
          <Card key={name}>
            <CardTitle>{name}</CardTitle>
            <p className="mt-3 text-2xl font-semibold">NO TRADE</p>
            <p className="mt-1 text-sm text-muted">Nothing to show yet.</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
