import type { SchemaSearchResult } from '@/api/openapi.gen'
import { ProductImage } from '@/components/ProductImage'
import { cn } from '@/lib/utils'
import { Info, SquareArrowOutUpRight } from 'lucide-react'

const CHARACTERISTICS_PREVIEW_LIMIT = 5
const RELEVANCE_THRESHOLD = -5.251

function formatRerankScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'неизвестна'
  return score.toFixed(2).replace('.', ',')
}

function IrrelevanceInfoBadge({ score }: { score: number | null | undefined }) {
  return (
    <div className="group/irrelevance absolute right-2 top-2 z-20">
      <button
        aria-label="Почему товар помечен как нерелевантный"
        className="flex size-7 cursor-help items-center justify-center rounded-full border border-slate-200 bg-white/95 text-slate-500 shadow-sm transition hover:text-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
        type="button"
      >
        <Info aria-hidden="true" className="size-4" />
      </button>
      <div
        className="pointer-events-none absolute right-0 top-full z-30 mt-2 w-72 rounded-md bg-slate-800 px-3 py-2 text-xs leading-5 text-white opacity-0 shadow-md transition-opacity group-hover/irrelevance:opacity-100 group-focus-within/irrelevance:opacity-100"
        role="tooltip"
      >
        <p className="font-medium">Товар помечен как нерелевантный</p>
        <p className="mt-1 text-white/90">
          После получения результатов с маркетплейса мы прогоняем их через модель реранжирования{' '}
          <span className="whitespace-nowrap">DiTy/cross-encoder-russian-msmarco</span>. Она сравнивает ваш
          запрос в форме «купить …» с названием каждого товара и выставляет
          оценку релевантности.
        </p>
        <p className="mt-2 text-white/90">
          Товар считается релевантным, если его оценка не ниже{' '}
          {RELEVANCE_THRESHOLD.toString().replace('.', ',')}. Оценка этого товара:{' '}
          <span className="font-medium text-white">{formatRerankScore(score)}</span>.
        </p>
      </div>
    </div>
  )
}

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
  const isIrrelevant = product.relevant === false

  return (
    <article
      className={cn('relative overflow-visible rounded-lg border border-slate-200 bg-white', className)}
    >
      {isIrrelevant ? <IrrelevanceInfoBadge score={product.rerank_score} /> : null}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute bottom-2 right-2 z-20 select-all font-mono text-[10px] leading-none text-transparent"
      >
        {product.rerank_score?.toFixed(4) ?? '—'}
      </span>
      <div
        className={cn(
          'overflow-hidden rounded-lg',
          isIrrelevant && 'opacity-55 saturate-50 blur-[0.4px]'
        )}
      >
        <ProductImage
          alt={product.name}
          gallerySrcs={product.image_links ?? []}
          primarySrc={product.image_link ?? null}
        />
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
      </div>
    </article>
  )
}
