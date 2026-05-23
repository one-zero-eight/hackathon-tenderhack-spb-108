import { ImageOff } from 'lucide-react'
import { useEffect, useState, type MouseEvent } from 'react'

const MAX_GALLERY_IMAGES = 6
const DOT_SHIFT_PX = 6

export function ProductImage({
  primarySrc,
  gallerySrcs,
  alt
}: {
  primarySrc: string | null
  gallerySrcs: string[]
  alt: string
}) {
  const visibleGallerySrcs = gallerySrcs.slice(0, MAX_GALLERY_IMAGES)
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const [failedSrcs, setFailedSrcs] = useState<string[]>([])
  const [isHovered, setIsHovered] = useState(false)

  useEffect(() => {
    setActiveIndex(null)
    setFailedSrcs([])
    setIsHovered(false)
  }, [primarySrc, gallerySrcs])

  const activeGallerySrc =
    activeIndex !== null && visibleGallerySrcs[activeIndex] ? visibleGallerySrcs[activeIndex] : null
  const safePrimarySrc = primarySrc && !failedSrcs.includes(primarySrc) ? primarySrc : null
  const safeActiveGallerySrc =
    activeGallerySrc && !failedSrcs.includes(activeGallerySrc) ? activeGallerySrc : null
  const displayedSrc = safeActiveGallerySrc ?? safePrimarySrc
  const hasGallery = visibleGallerySrcs.length > 0
  const indicatorOffset =
    activeIndex === null ? 0 : ((visibleGallerySrcs.length - 1) / 2 - activeIndex) * DOT_SHIFT_PX

  const handleMouseMove = (event: MouseEvent<HTMLDivElement>) => {
    if (!hasGallery) return

    const bounds = event.currentTarget.getBoundingClientRect()
    if (bounds.width <= 0) return

    const relativeX = Math.min(Math.max(event.clientX - bounds.left, 0), bounds.width)
    const nextIndex = Math.min(
      visibleGallerySrcs.length - 1,
      Math.floor((relativeX / bounds.width) * visibleGallerySrcs.length)
    )

    setActiveIndex((currentIndex) => (currentIndex === nextIndex ? currentIndex : nextIndex))
  }

  const handleMouseEnter = () => {
    if (!hasGallery) return
    setIsHovered(true)
  }

  const handleMouseLeave = () => {
    setIsHovered(false)
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
      className="group relative h-80 w-full overflow-hidden bg-white"
      onMouseEnter={handleMouseEnter}
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
      {hasGallery ? (
        <div
          className={`pointer-events-none absolute inset-x-0 bottom-3 flex justify-center transition-opacity duration-200 ${
            isHovered ? 'opacity-100' : 'opacity-0'
          }`}
        >
          <div
            className="flex items-center gap-2 rounded-full bg-black/10 px-3 py-1.5 backdrop-blur-sm transition-transform duration-200"
            style={{
              transform: `translateX(${indicatorOffset}px)`
            }}
          >
            {visibleGallerySrcs.map((src, index) => (
              <span
                aria-hidden="true"
                className={`block rounded-full bg-white transition-all duration-200 ${
                  activeIndex === index ? 'h-2.5 w-2.5 scale-125 opacity-100' : 'h-2 w-2 opacity-80'
                }`}
                key={src}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
