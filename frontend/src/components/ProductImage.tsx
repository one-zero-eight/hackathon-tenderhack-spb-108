import { ImageOff } from 'lucide-react'
import { useState } from 'react'

export function ProductImage({ src, alt }: { src: string | null; alt: string }) {
  const [hasError, setHasError] = useState(false)

  if (!src || hasError) {
    return (
      <div className="flex h-44 w-full flex-col items-center justify-center gap-2 bg-slate-100 px-4 text-center text-sm text-slate-500">
        <ImageOff aria-hidden="true" className="size-8 text-slate-400" />
        <span>{alt}</span>
      </div>
    )
  }

  return (
    <img
      alt={alt}
      className="h-44 w-full object-cover"
      loading="lazy"
      onError={() => setHasError(true)}
      src={src}
    />
  )
}
