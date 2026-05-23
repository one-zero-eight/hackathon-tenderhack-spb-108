import { $api } from '@/api'
import { SourceType } from '@/api/openapi.gen'
import { ProductCard } from '@/components/ProductCard'
import { ProductSourceDetails } from '@/components/ProductSourceDetails'
import { ProductSourceSkeletonList } from '@/components/ProductSourceSkeleton'
import { RegionDropdown } from '@/components/RegionDropdown'
import { Button } from '@/components/ui/button'
import { mapSearchSourceToGroup } from '@/lib/mapping'
import { ALL_REGIONS, regionCapitalByName, type RegionName } from '@/lib/regions'
import type { SearchResultProduct, SearchResultsWithTypofix, SortMode } from '@/lib/types'
import { parsePrice, sourceTypesForRunetSearch } from '@/lib/utils'
import { createFileRoute } from '@tanstack/react-router'
import { Info, LoaderCircle, Search } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'

export const Route = createFileRoute('/')({ component: Home })

function Home() {
  const searchInputRef = useRef<HTMLInputElement>(null)
  const [searchParams, setSearchParams] = useState<{
    query: string
    region: string | null
    source_types: SourceType[] | null
    short: boolean
  } | null>(null)
  const [sortMode, setSortMode] = useState<SortMode>('sources')
  const [selectedRegion, setSelectedRegion] = useState<RegionName>(ALL_REGIONS)
  const [extendedRunetSearch, setExtendedRunetSearch] = useState(false)
  const {
    mutate,
    data: searchResults,
    error,
    isPending
  } = $api.useMutation('post', '/search/search')
  const apiSourceGroups = searchResults?.sources.map(mapSearchSourceToGroup)
  const visibleGroups = apiSourceGroups ?? []
  const typofixSuggestions =
    (searchResults as SearchResultsWithTypofix | undefined)?.typofix_suggestions ?? []
  const uniqueTypofixSuggestions = [
    ...new Set(typofixSuggestions.map(({ suggestion }) => suggestion))
  ]
  const typofixSuggestionBySource = new Map(
    typofixSuggestions.map(({ source, suggestion }) => [source, suggestion] as const)
  )
  const originalQuery =
    searchResults?.original_params.query ??
    searchParams?.query ??
    searchInputRef.current?.value?.trim() ??
    ''
  const hasTypofixSuggestions = typofixSuggestions.length > 0

  const totalProducts = visibleGroups.reduce((sum, group) => sum + group.products.length, 0)
  const allProducts: SearchResultProduct[] = visibleGroups.flatMap((group) =>
    group.products.map((product) => ({
      product,
      sourceType: group.sourceType,
      sourceTitle: group.title,
      sourceUrl: group.sourceUrl,
      sourceLogoUrl: group.logoUrl,
      parsedPrice: parsePrice(product.price)
    }))
  )
  const sortedProducts =
    sortMode === 'sources'
      ? []
      : [...allProducts].sort((left, right) => {
          if (left.parsedPrice === null && right.parsedPrice === null) return 0
          if (left.parsedPrice === null) return 1
          if (right.parsedPrice === null) return -1

          return sortMode === 'price-asc'
            ? left.parsedPrice - right.parsedPrice
            : right.parsedPrice - left.parsedPrice
        })

  const allPrices = visibleGroups.flatMap((group) =>
    group.products.map((p) => parsePrice(p.price)).filter((p): p is number => p !== null)
  )
  const averagePrice =
    allPrices.length > 0 ? allPrices.reduce((sum, p) => sum + p, 0) / allPrices.length : null

  const showSkeleton = isPending && Boolean(searchParams)

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const query = searchInputRef.current?.value.trim() ?? ''

    if (!query) return

    setSearchParams({
      query,
      region: selectedRegion === ALL_REGIONS ? null : regionCapitalByName[selectedRegion],
      source_types: sourceTypesForRunetSearch(extendedRunetSearch),
      short: false
    })
    mutate({
      body: {
        query,
        region: selectedRegion === ALL_REGIONS ? null : regionCapitalByName[selectedRegion],
        source_types: sourceTypesForRunetSearch(extendedRunetSearch),
        short: false
      }
    })
  }

  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-3">
          <div className="max-w-3xl">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
              Поиск товаров по Рунету
            </h1>
          </div>
        </header>

        <form
          aria-label="Фильтры каталога"
          className="grid gap-4 rounded-lg bg-white p-4 md:grid-cols-[minmax(0,1fr)_320px_260px]"
          onSubmit={handleSearchSubmit}
        >
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium text-slate-700">Строка поиска</span>
            <span className="relative">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-slate-400"
              />
              <input
                className="h-11 w-full rounded-md border border-slate-300 bg-white pl-10 pr-3 text-sm outline-none transition focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                placeholder="Введите товар или характеристику"
                ref={searchInputRef}
                required
                type="search"
              />
            </span>
          </label>

          <RegionDropdown onSelect={setSelectedRegion} selectedRegion={selectedRegion} />

          <div className="flex flex-col gap-2">
            <span className="invisible text-sm font-medium">Search</span>
            <Button className="h-11 w-full gap-2 px-4 text-sm" disabled={isPending} type="submit">
              {isPending ? (
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Search aria-hidden="true" className="size-4" />
              )}
              {isPending ? 'Ищем...' : 'Найти'}
            </Button>
            <label className="mt-1 flex cursor-pointer items-center justify-between gap-3">
              <span className="text-sm font-medium text-slate-700">
                Расширенный поиск по Рунету
              </span>
              <span className="relative inline-flex h-6 w-11 shrink-0">
                <input
                  checked={extendedRunetSearch}
                  className="peer sr-only"
                  onChange={(event) => setExtendedRunetSearch(event.target.checked)}
                  type="checkbox"
                />
                <span
                  aria-hidden="true"
                  className="absolute inset-0 rounded-full bg-slate-200 transition peer-focus-visible:ring-2 peer-focus-visible:ring-slate-900/10 peer-checked:bg-slate-900"
                />
                <span
                  aria-hidden="true"
                  className="absolute left-0.5 top-0.5 size-5 rounded-full bg-white shadow-sm transition peer-checked:translate-x-5"
                />
              </span>
            </label>
          </div>
        </form>

        {hasTypofixSuggestions ? (
          <p className="text-sm text-slate-600">
            Возможно, вы имели в виду{' '}
            {uniqueTypofixSuggestions.map((suggestion) => `"${suggestion}"`).join(', ')}
          </p>
        ) : null}

        <section
          aria-busy={isPending}
          aria-label="Источники товаров"
          className="flex flex-col gap-4"
        >
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">Основные источники</h2>
              <p className="text-sm text-slate-600">Регион: {selectedRegion}</p>
            </div>
            <div className="flex flex-col items-end gap-1">
              {averagePrice !== null && !isPending && (
                <div className="flex items-center gap-1.5 text-sm font-medium text-slate-700">
                  <span>Средняя цена: {Math.round(averagePrice).toLocaleString('ru-RU')} ₽</span>
                  <div className="group relative flex items-center">
                    <Info className="size-4 text-slate-400 hover:text-slate-600 cursor-help" />
                    <div className="pointer-events-none absolute right-0 top-full z-10 mt-1 w-64 opacity-0 transition-opacity group-hover:opacity-100 rounded-md bg-slate-800 px-3 py-2 text-xs text-white shadow-md">
                      Средняя цена рассчитывается как сумма цен всех найденных товаров, делённая на
                      их количество. Учтено товаров с известной ценой: {allPrices.length}
                    </div>
                  </div>
                </div>
              )}
              <p className="text-sm text-slate-500">
                {isPending ? 'Идёт поиск...' : `Найдено товаров: ${totalProducts}`}
              </p>
            </div>
          </div>

          {!showSkeleton && totalProducts > 0 ? (
            <div className="flex flex-wrap gap-2">
              <Button
                className="px-4"
                onClick={() => setSortMode('sources')}
                type="button"
                variant={sortMode === 'sources' ? 'default' : 'outline'}
              >
                По источникам
              </Button>
              <Button
                className="px-4"
                onClick={() => setSortMode('price-asc')}
                type="button"
                variant={sortMode === 'price-asc' ? 'default' : 'outline'}
              >
                Цена: по возрастанию
              </Button>
              <Button
                className="px-4"
                onClick={() => setSortMode('price-desc')}
                type="button"
                variant={sortMode === 'price-desc' ? 'default' : 'outline'}
              >
                Цена: по убыванию
              </Button>
            </div>
          ) : null}

          {error ? (
            <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              Не удалось выполнить поиск. Попробуйте ещё раз.
            </p>
          ) : null}

          {showSkeleton ? <ProductSourceSkeletonList /> : null}

          {!showSkeleton && sortMode === 'sources'
            ? visibleGroups.map((group) => (
                <ProductSourceDetails
                  group={group}
                  key={group.title}
                  queryResultLabel={
                    hasTypofixSuggestions
                      ? `Результат запроса по "${
                          typofixSuggestionBySource.get(group.sourceType) ?? originalQuery
                        }"`
                      : null
                  }
                />
              ))
            : null}

          {!showSkeleton && sortMode !== 'sources' ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {sortedProducts.map((item, index) => (
                <div
                  className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
                  key={`${item.sourceType}-${item.product.productLink ?? item.product.title}-${index}`}
                >
                  <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex min-w-0 items-center gap-3">
                      <img
                        alt=""
                        className="size-9 shrink-0 rounded-md border border-slate-200 bg-white object-contain p-1"
                        loading="lazy"
                        src={item.sourceLogoUrl}
                      />
                      <span className="truncate text-sm font-semibold text-slate-900">
                        {item.sourceTitle}
                      </span>
                    </div>
                    <a
                      className="shrink-0 text-sm font-medium text-slate-600 transition hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
                      href={item.sourceUrl}
                      rel="noreferrer"
                      target="_blank"
                    >
                      Источник
                    </a>
                  </div>
                  <ProductCard className="rounded-none border-0" product={item.product} />
                </div>
              ))}
            </div>
          ) : null}
        </section>
      </section>
    </main>
  )
}
