/** Consistent skeleton loading placeholders (Phase: frontend polish). Used
 * in place of bare spinner text so loading states feel like a real product
 * rather than a debug placeholder. */

export function SkeletonBlock({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-board-800/70 ${className}`} />
}

export function SkeletonBoardExplorer() {
  return (
    <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.8fr)_280px_360px]">
      <SkeletonBlock className="h-[560px]" />
      <div className="flex flex-col gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonBlock key={i} className="h-24" />
        ))}
      </div>
      <SkeletonBlock className="h-[560px]" />
    </div>
  )
}
