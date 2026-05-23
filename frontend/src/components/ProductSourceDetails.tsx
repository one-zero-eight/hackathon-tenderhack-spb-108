import { ProductImage } from '@/components/ProductImage'
import type { MarketplaceGroup } from '@/lib/types'
import { SquareArrowOutUpRight } from 'lucide-react'
import { useState } from 'react'

const CHARACTERISTICS_PREVIEW_LIMIT = 5
const PRODUCTS_PER_PAGE = 3

export function ProductCharacteristics({ characteristics }: { characteristics: string[] }) {
  const hasHiddenCharacteristics = characteristics.length > CHARACTERISTICS_PREVIEW_LIMIT
  const previewCharacteristics = characteristics.slice(0, CHARACTERISTICS_PREVIEW_LIMIT)
  const hiddenCharacteristics = characteristics.slice(CHARACTERISTICS_PREVIEW_LIMIT)

  if (characteristics.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-2">
      <ul className="space-y-1 text-sm text-slate-600">
        {previewCharacteristics.map((characteristic) => (
          <li className="border-l border-slate-200 pl-3 leading-5" key={characteristic}>
            {characteristic}
          </li>
        ))}
      </ul>
      {hasHiddenCharacteristics ? (
        <details className="group/characteristics">
          <summary className="w-fit cursor-pointer list-none text-sm font-medium text-slate-900 underline underline-offset-2 transition marker:hidden hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-900/10">
            <span className="group-open/characteristics:hidden">Показать все</span>
            <span className="hidden group-open/characteristics:inline">Скрыть</span>
          </summary>
          <ul className="mt-2 space-y-1 text-sm text-slate-600">
            {hiddenCharacteristics.map((characteristic) => (
              <li className="border-l border-slate-200 pl-3 leading-5" key={characteristic}>
                {characteristic}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  )
}

export function ProductSourceDetails({ group }: { group: MarketplaceGroup }) {
  const [page, setPage] = useState(0)
  const pageCount = Math.ceil(group.products.length / PRODUCTS_PER_PAGE)
  const currentPage = Math.min(page, Math.max(pageCount - 1, 0))
  const visibleProducts = group.products.slice(
    currentPage * PRODUCTS_PER_PAGE,
    (currentPage + 1) * PRODUCTS_PER_PAGE
  )
  const canPaginate = pageCount > 1

  return (
    <details className="group rounded-lg border border-slate-200 bg-white shadow-sm" open>
      <summary className="flex cursor-pointer list-none flex-col gap-4 px-4 py-4 marker:hidden sm:flex-row sm:items-center sm:justify-between">
        <span className="flex min-w-0 items-center gap-3 self-stretch sm:self-auto">
          <img
            alt=""
            className="size-10 shrink-0 rounded-md border border-slate-200 bg-white object-contain p-1"
            loading="lazy"
            src={group.logoUrl}
          />
          <span className="min-w-0">
            <span className="block truncate text-base font-semibold text-slate-950">
              {group.title}
            </span>
          </span>
        </span>
        <span className="flex items-center justify-between gap-3 self-stretch sm:shrink-0 sm:self-auto">
          <a
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-center text-sm font-medium text-slate-800 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
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
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visibleProducts.map((product) => (
                <article
                  className="overflow-hidden rounded-lg border border-slate-200 bg-white"
                  key={`${product.title}-${product.productLink ?? ''}`}
                >
                  <ProductImage alt={product.title} src={product.image} />
                  <div className="flex flex-col gap-3 p-4">
                    {product.productLink ? (
                      <a
                        className="flex items-start gap-1.5 text-base font-semibold leading-6 text-slate-950 transition hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
                        href={product.productLink}
                        rel="noreferrer"
                        target="_blank"
                      >
                        <span className="line-clamp-2 min-w-0">{product.title}</span>
                        <SquareArrowOutUpRight
                          aria-hidden="true"
                          className="mt-1 size-4 shrink-0 text-slate-400"
                        />
                      </a>
                    ) : (
                      <h3 className="line-clamp-2 text-base font-semibold leading-6 text-slate-950">
                        {product.title}
                      </h3>
                    )}
                    {product.price ? (
                      <p className="text-sm font-medium text-slate-900">{product.price} ₽</p>
                    ) : null}
                    {product.rating || product.reviews ? (
                      <p className="text-sm text-slate-600">
                        {[product.rating ? `${product.rating} ★` : null, product.reviews]
                          .filter(Boolean)
                          .join(' · ')}
                      </p>
                    ) : null}
                    <ProductCharacteristics characteristics={product.characteristics} />
                  </div>
                </article>
              ))}
            </div>
            {canPaginate ? (
              <div className="flex items-center justify-center gap-3">
                <button
                  className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={currentPage === 0}
                  onClick={() => setPage((current) => Math.max(current - 1, 0))}
                  type="button"
                >
                  Назад
                </button>
                <span className="text-sm text-slate-600">
                  {currentPage + 1} / {pageCount}
                </span>
                <button
                  className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={currentPage >= pageCount - 1}
                  onClick={() => setPage((current) => Math.min(current + 1, pageCount - 1))}
                  type="button"
                >
                  Вперёд
                </button>
              </div>
            ) : null}
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
