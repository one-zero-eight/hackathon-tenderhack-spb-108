import { ProductCard } from '@/components/ProductCard'
import type { MarketplaceGroup } from '@/lib/types'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'

const PRODUCTS_PER_PAGE = 3

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
    <details className="group rounded-lg border border-slate-200 bg-white shadow-sm" open>
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
              <span className="truncate text-base font-semibold text-slate-950">{group.title}</span>
              {minPrice !== null && (
                <span className="text-sm font-medium text-slate-900">
                  от {minPrice.toLocaleString('ru-RU')} ₽
                </span>
              )}
              {queryResultLabel ? (
                <span className="text-xs font-medium text-slate-500">{queryResultLabel}</span>
              ) : null}
            </span>
          </span>
        </span>
        <span className="flex items-center justify-between gap-3 self-stretch sm:shrink-0 sm:self-auto">
          <a
            className="cursor-pointer rounded-md border border-slate-300 bg-white px-3 py-1.5 text-center text-sm font-medium text-slate-800 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
            href={group.sourceUrl}
            onClick={(event) => event.stopPropagation()}
            rel="noreferrer"
            target="_blank"
          >
            Перейти на маркетплейс
          </a>
          <span className="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600">
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
                    key={`${product.title}-${product.productLink ?? ''}`}
                    product={product}
                  />
                ))}
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
