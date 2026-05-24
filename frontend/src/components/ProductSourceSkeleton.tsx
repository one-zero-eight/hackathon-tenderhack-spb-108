const SKELETON_GROUPS = 3
const SKELETON_PRODUCTS_PER_GROUP = 3

function SkeletonBlock({ className }: { className: string }) {
  return <div className={`animate-pulse rounded-md bg-slate-200 ${className}`} />
}

function ProductCardSkeleton() {
  return (
    <article className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <SkeletonBlock className="h-44 w-full rounded-none" />
      <div className="flex flex-col gap-3 p-4">
        <SkeletonBlock className="h-5 w-4/5" />
        <SkeletonBlock className="h-4 w-1/3" />
        <SkeletonBlock className="h-4 w-1/2" />
        <div className="flex flex-col gap-2 pt-1">
          <SkeletonBlock className="h-4 w-full" />
          <SkeletonBlock className="h-4 w-11/12" />
          <SkeletonBlock className="h-4 w-3/4" />
        </div>
      </div>
    </article>
  )
}

export function ProductSourceSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="rounded-lg border border-slate-200 bg-white shadow-sm"
    >
      <div className="flex flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <SkeletonBlock className="size-10 shrink-0 rounded-md" />
          <div className="flex min-w-0 flex-col gap-2">
            <SkeletonBlock className="h-5 w-40" />
            <SkeletonBlock className="h-3 w-56" />
          </div>
        </div>
        <div className="flex items-center justify-between gap-3 sm:shrink-0">
          <SkeletonBlock className="h-9 w-44" />
          <SkeletonBlock className="h-8 w-10 rounded-full" />
        </div>
      </div>

      <div className="border-t border-slate-200 p-4">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: SKELETON_PRODUCTS_PER_GROUP }, (_, productIndex) => (
            <ProductCardSkeleton key={productIndex} />
          ))}
        </div>
      </div>
    </div>
  )
}

export function ProductSourceSkeletonList() {
  return (
    <>
      {Array.from({ length: SKELETON_GROUPS }, (_, groupIndex) => (
        <ProductSourceSkeleton key={groupIndex} />
      ))}
    </>
  )
}
