import { Button } from '@/components/ui/button'
import { ArrowUp } from 'lucide-react'
import { useEffect, useState } from 'react'

const VISIBILITY_OFFSET = 160

export function ScrollToTopButton() {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const updateVisibility = () => {
      setIsVisible(window.scrollY > VISIBILITY_OFFSET)
    }

    updateVisibility()
    window.addEventListener('scroll', updateVisibility, { passive: true })

    return () => window.removeEventListener('scroll', updateVisibility)
  }, [])

  const handleScrollToTop = () => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    window.scrollTo({
      top: 0,
      behavior: prefersReducedMotion ? 'auto' : 'smooth'
    })
  }

  return (
    <div
      className={[
        'pointer-events-none fixed left-4 z-[70] transition-all duration-200 sm:left-auto sm:right-6',
        'bottom-[calc(env(safe-area-inset-bottom,0px)+1rem)] sm:bottom-6',
        isVisible ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0'
      ].join(' ')}
    >
      <Button
        aria-label="Прокрутить страницу вверх"
        className={[
          'pointer-events-auto h-12 min-w-12 touch-manipulation rounded-full px-3 shadow-lg shadow-slate-900/15',
          'sm:h-11 sm:rounded-lg sm:px-4'
        ].join(' ')}
        onClick={handleScrollToTop}
        type="button"
      >
        <ArrowUp aria-hidden="true" className="size-4" />
        <span className="sr-only sm:not-sr-only">Вверх</span>
      </Button>
    </div>
  )
}
