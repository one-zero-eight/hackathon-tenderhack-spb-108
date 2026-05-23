import { ImageOff } from 'lucide-react'
import { useEffect, useState, type MouseEvent } from 'react'

export function ProductImage({
  primarySrc,
  gallerySrcs,
  alt
}: {
  primarySrc: string | null
  gallerySrcs: string[]
  alt: string
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const [failedSrcs, setFailedSrcs] = useState<string[]>([])

  useEffect(() => {
    setActiveIndex(null)
    setFailedSrcs([])
  }, [primarySrc, gallerySrcs])

  const activeGallerySrc =
    activeIndex !== null && gallerySrcs[activeIndex] ? gallerySrcs[activeIndex] : null
  const safePrimarySrc = primarySrc && !failedSrcs.includes(primarySrc) ? primarySrc : null
  const safeActiveGallerySrc =
    activeGallerySrc && !failedSrcs.includes(activeGallerySrc) ? activeGallerySrc : null
  const displayedSrc = safeActiveGallerySrc ?? safePrimarySrc
  const hasGallery = gallerySrcs.length > 0

  const handleMouseMove = (event: MouseEvent<HTMLDivElement>) => {
    if (!hasGallery) return

    const bounds = event.currentTarget.getBoundingClientRect()
    if (bounds.width <= 0) return

    const relativeX = Math.min(Math.max(event.clientX - bounds.left, 0), bounds.width)
    const nextIndex = Math.min(
      gallerySrcs.length - 1,
      Math.floor((relativeX / bounds.width) * gallerySrcs.length)
    )

    setActiveIndex((currentIndex) => (currentIndex === nextIndex ? currentIndex : nextIndex))
  }

  const handleMouseLeave = () => {
    setActiveIndex(null)
  }

  if (!displayedSrc) {
    return (
      <div className="flex h-80 w-full flex-col items-center justify-center gap-2 bg-slate-100 px-4 text-center text-sm text-slate-500">
        <ImageOff aria-hidden="true" className="size-8 text-slate-400" />
        <span>{alt}</span>
      </div>
    )
  }

  return (
    <div
      className="h-80 w-full bg-white"
      onMouseLeave={handleMouseLeave}
      onMouseMove={handleMouseMove}
    >
      <img
        alt={alt}
        className="h-full w-full object-contain"
        loading="lazy"
        onError={() => {
          setFailedSrcs((current) =>
            displayedSrc && !current.includes(displayedSrc) ? [...current, displayedSrc] : current
          )
        }}
        src={displayedSrc}
      />
    </div>
  )
}
