import { SourceType } from '@/api/openapi.gen'
import { ProductCard } from '@/components/ProductCard'
import type { MarketplaceGroup } from '@/lib/types'
import { cn } from '@/lib/utils'
import { ChevronLeft, ChevronRight, SquareArrowOutUpRight } from 'lucide-react'
import { useState } from 'react'

const PRODUCTS_PER_PAGE = 3

export function getMarketplaceTheme(sourceType: SourceType) {
  switch (sourceType) {
    case SourceType.ozon:
      const ozonGradient = 'linear-gradient(135deg, rgb(0 91 255 / 80%), rgb(252 64 55 / 80%))'
      return {
        summaryGradient: ozonGradient,
        summaryStyle: { backgroundImage: ozonGradient },
        titleClassName: 'text-slate-950',
        metaClassName: 'text-slate-900',
        queryClassName: 'text-slate-600',
        buttonClassName:
          'border-slate-300 bg-white/90 text-slate-800 hover:bg-white focus:ring-slate-900/10',
        countClassName: 'border-slate-200 bg-white/70 text-slate-700'
      }
    case SourceType.wildberries:
      const wildberriesGradient =
        'linear-gradient(135deg, rgb(127 48 227 / 80%), rgb(249 4 121 / 80%))'
      return {
        summaryGradient: wildberriesGradient,
        summaryStyle: { backgroundImage: wildberriesGradient },
        titleClassName: 'text-white',
        metaClassName: 'text-white',
        queryClassName: 'text-white/85',
        buttonClassName:
          'border-white/40 bg-white/15 text-white hover:bg-white/25 focus:ring-white/30',
        countClassName: 'border-white/30 bg-white/15 text-white'
      }
    case SourceType.yandex_market:
      const yandexMarketGradient =
        'linear-gradient(135deg, rgb(255 204 0 / 80%), rgb(255 0 0 / 80%))'
      return {
        summaryGradient: yandexMarketGradient,
        summaryStyle: { backgroundImage: yandexMarketGradient },
        titleClassName: 'text-slate-950',
        metaClassName: 'text-slate-900',
        queryClassName: 'text-slate-600',
        buttonClassName:
          'border-slate-300 bg-white/90 text-slate-800 hover:bg-white focus:ring-slate-900/10',
        countClassName: 'border-slate-200 bg-white/70 text-slate-700'
      }
    default:
      return {
        summaryGradient: null,
        summaryStyle: undefined,
        titleClassName: 'text-slate-950',
        metaClassName: 'text-slate-900',
        queryClassName: 'text-slate-500',
        buttonClassName:
          'border-slate-300 bg-white text-slate-800 hover:bg-slate-100 focus:ring-slate-900/10',
        countClassName: 'border-slate-200 text-slate-600'
      }
  }
}

function SeeMoreMarketplaceCard({ href }: { href: string }) {
  return (
    <a
      className="flex min-h-[500px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center transition hover:border-slate-400 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
      href={href}
      rel="noreferrer"
      target="_blank"
    >
      <SquareArrowOutUpRight aria-hidden="true" className="size-8 text-slate-400" />
      <span className="text-base font-semibold text-slate-900">Посмотреть ещё</span>
      <span className="text-sm text-slate-500">Открыть все результаты на маркетплейсе</span>
    </a>
  )
}

export function ProductSourceDetails({
  group,
  queryResultLabel
}: {
  group: MarketplaceGroup
  queryResultLabel?: string | null
}) {
  const [page, setPage] = useState(0)
  const pageCount = Math.ceil(group.products.length / PRODUCTS_PER_PAGE)
  const currentPage = Math.min(page, Math.max(pageCount - 1, 0))
  const visibleProducts = group.products.slice(
    currentPage * PRODUCTS_PER_PAGE,
    (currentPage + 1) * PRODUCTS_PER_PAGE
  )
  const canPaginate = pageCount > 1
  const isLastPage = currentPage >= pageCount - 1
  const theme = getMarketplaceTheme(group.sourceType)

  const minPrice = group.products.reduce(
    (min, product) => {
      if (!product.price) return min
      const price = Number.parseInt(product.price.replace(/\D/g, ''), 10)
      if (Number.isNaN(price)) return min
      return min === null ? price : Math.min(min, price)
    },
    null as number | null
  )

  return (
    <details
      className="group rounded-lg border border-slate-200 bg-white shadow-sm"
      open
      style={theme.summaryStyle}
    >
      <summary className="flex list-none flex-col gap-4 px-4 py-4 marker:hidden sm:flex-row sm:items-center sm:justify-between">
        <span className="flex min-w-0 items-center gap-3 self-stretch sm:self-auto">
          <img
            alt=""
            className="size-10 shrink-0 rounded-md border border-slate-200 bg-white object-contain p-1"
            loading="lazy"
            src={group.logoUrl}
          />
          <span className="min-w-0">
            <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <span className={cn('truncate text-base font-semibold', theme.titleClassName)}>
                {group.title}
              </span>
              {minPrice !== null && (
                <span className={cn('text-sm font-medium', theme.metaClassName)}>
                  от {minPrice.toLocaleString('ru-RU')} ₽
                </span>
              )}
              {queryResultLabel ? (
                <span className={cn('text-xs font-medium', theme.queryClassName)}>
                  {queryResultLabel}
                </span>
              ) : null}
            </span>
          </span>
        </span>
        <span className="flex items-center justify-between gap-3 self-stretch sm:shrink-0 sm:self-auto">
          <a
            className={cn(
              'cursor-pointer rounded-md border px-3 py-1.5 text-center text-sm font-medium transition focus:outline-none focus:ring-2',
              theme.buttonClassName
            )}
            href={group.sourceUrl}
            onClick={(event) => event.stopPropagation()}
            rel="noreferrer"
            target="_blank"
          >
            Перейти на маркетплейс
          </a>
          <span
            className={cn(
              'rounded-full border px-3 py-1 text-sm backdrop-blur-[2px]',
              theme.countClassName
            )}
          >
            {group.products.length}
          </span>
        </span>
      </summary>

      <div className="border-t border-slate-200 p-4">
        {group.products.length > 0 ? (
          <div className="flex flex-col gap-4">
            <div className="relative">
              <div className="grid min-h-[500px] gap-4 md:grid-cols-2 xl:grid-cols-3">
                {visibleProducts.map((product) => (
                  <ProductCard
                    key={`${product.name}-${product.product_link ?? ''}`}
                    product={product}
                  />
                ))}
                {isLastPage ? <SeeMoreMarketplaceCard href={group.sourceUrl} /> : null}
              </div>

              {canPaginate && currentPage > 0 && (
                <button
                  aria-label="Назад"
                  className="absolute -left-3 top-[160px] cursor-pointer flex size-12 -translate-y-1/2 items-center justify-center rounded-full border border-slate-200 bg-white shadow-lg transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-900/10 z-20 sm:-left-6"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setPage((current) => Math.max(current - 1, 0))
                  }}
                  type="button"
                >
                  <ChevronLeft className="size-8 text-slate-900" />
                </button>
              )}

              {canPaginate && currentPage < pageCount - 1 && (
                <button
                  aria-label="Вперёд"
                  className="absolute -right-3 top-[160px] cursor-pointer flex size-12 -translate-y-1/2 items-center justify-center rounded-full border border-slate-200 bg-white shadow-lg transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-900/10 z-20 sm:-right-6"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setPage((current) => Math.min(current + 1, pageCount - 1))
                  }}
                  type="button"
                >
                  <ChevronRight className="size-8 text-slate-900" />
                </button>
              )}
            </div>
          </div>
        ) : (
          <p className="rounded-md bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
            Ничего не найдено по текущему запросу.
          </p>
        )}
      </div>
    </details>
  )
}
