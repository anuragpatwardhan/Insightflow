export function CardSkeleton() {
  return (
    <div className="rounded-2xl border border-border bg-grad-panel p-5 shadow-card">
      <div className="flex items-center gap-2 mb-3">
        <div className="skeleton animate-shimmer h-5 w-16" />
        <div className="skeleton animate-shimmer h-5 w-14" />
        <div className="skeleton animate-shimmer h-4 w-24" />
      </div>
      <div className="skeleton animate-shimmer h-5 w-3/4 mb-3" />
      <div className="space-y-1.5 mb-4">
        <div className="skeleton animate-shimmer h-3 w-full" />
        <div className="skeleton animate-shimmer h-3 w-5/6" />
      </div>
      <div className="skeleton animate-shimmer h-10 w-full mb-4" />
      <div className="space-y-2">
        <div className="skeleton animate-shimmer h-2.5 w-full" />
        <div className="skeleton animate-shimmer h-2.5 w-5/6" />
        <div className="skeleton animate-shimmer h-2.5 w-4/6" />
      </div>
    </div>
  );
}

export function FeedSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="grid gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}
