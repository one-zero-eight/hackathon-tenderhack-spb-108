import type { SchemaSearchResult } from '@/api/openapi.gen'
import { ProductImage } from '@/components/ProductImage'
import { SquareArrowOutUpRight } from 'lucide-react'

const CHARACTERISTICS_PREVIEW_LIMIT = 5

export function ProductCharacteristics({
  characteristics
}: {
  characteristics: SchemaSearchResult['characteristics']
}) {
  const characteristicList = Object.entries(characteristics ?? {}).map(
    ([name, value]) => `${name}: ${value}`
  )
  const hasHiddenCharacteristics = characteristicList.length > CHARACTERISTICS_PREVIEW_LIMIT
  const previewCharacteristics = characteristicList.slice(0, CHARACTERISTICS_PREVIEW_LIMIT)
  const hiddenCharacteristics = characteristicList.slice(CHARACTERISTICS_PREVIEW_LIMIT)

  if (characteristicList.length === 0) {
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

export function ProductCard({
  product,
  className = ''
}: {
  product: SchemaSearchResult
  className?: string
}) {
  return (
    <article className={`overflow-hidden rounded-lg border border-slate-200 bg-white ${className}`}>
      <ProductImage alt={product.name} src={product.image_link ?? null} />
      <div className="flex flex-col gap-3 p-4">
        {product.product_link ? (
          <a
            className="cursor-pointer flex items-start gap-1.5 text-base font-semibold leading-6 text-slate-950 transition hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
            href={product.product_link}
            rel="noreferrer"
            target="_blank"
          >
            <span className="line-clamp-2 min-w-0">{product.name}</span>
            <SquareArrowOutUpRight
              aria-hidden="true"
              className="mt-1 size-4 shrink-0 text-slate-400"
            />
          </a>
        ) : (
          <h3 className="line-clamp-2 text-base font-semibold leading-6 text-slate-950">
            {product.name}
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
  )
}
