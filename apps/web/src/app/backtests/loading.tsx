export default function Loading() {
  return (
    <div className="space-y-4" aria-busy="true">
      <div className="h-8 w-44 animate-pulse rounded-lg bg-foreground/10" />
      <div className="grid gap-4 sm:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="glass h-52 animate-pulse rounded-2xl" />
        ))}
      </div>
    </div>
  );
}
