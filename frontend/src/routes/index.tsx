import { SourceType, SourceStatus } from '@/api/openapi.gen'
import { ProductCard } from '@/components/ProductCard'
import { ProductSourceDetails, getMarketplaceTheme } from '@/components/ProductSourceDetails'
import { ProductSourceSkeleton } from '@/components/ProductSourceSkeleton'
import { RegionDropdown } from '@/components/RegionDropdown'
import { SpellcheckSearchInput } from '@/components/SpellcheckSearchInput'
import { TypofixNotice } from '@/components/TypofixNotice'
import { Button } from '@/components/ui/button'
import { mapSearchSourceToGroup } from '@/lib/mapping'
import { ALL_REGIONS, regionCapitalByName, type RegionName } from '@/lib/regions'
import type { SearchResultProduct, SortMode } from '@/lib/types'
import { useSearchJob } from '@/lib/useSearchJob'
import { parsePrice, plannedSourceTypes, sourceTypesForRunetSearch, compareByParseReadiness, getSearchSourceReadyAt } from '@/lib/utils'
import { createFileRoute } from '@tanstack/react-router'
import { Info, LoaderCircle, Search } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'

type HomeSearch = {
  jobId?: number
}

function parseJobId(value: unknown): number | undefined {
  if (value === undefined || value === null || value === '') return undefined
  const jobId = Number(value)
  if (!Number.isInteger(jobId) || jobId <= 0) return undefined
  return jobId
}

function regionNameByCapital(capital: string | null | undefined): RegionName {
  if (!capital) return ALL_REGIONS
  const match = Object.entries(regionCapitalByName).find(([, name]) => name === capital)
  return (match?.[0] as RegionName | undefined) ?? ALL_REGIONS
}

export const Route = createFileRoute('/')({
  validateSearch: (search: Record<string, unknown>): HomeSearch => {
    const jobId = parseJobId(search.jobId)
    return jobId === undefined ? {} : { jobId }
  },
  component: Home
})

function Home() {
  const { jobId } = Route.useSearch()
  const navigate = Route.useNavigate()
  const setJobId = (nextJobId: number | undefined) => {
    void navigate({
      search: (prev) => {
        if (nextJobId === undefined) {
          const { jobId: _jobId, ...rest } = prev
          return rest
        }
        return { ...prev, jobId: nextJobId }
      },
      replace: true
    })
  }

  const searchInputRef = useRef<HTMLInputElement>(null)
  const hydratedJobIdRef = useRef<number | undefined>(undefined)
  const [query, setQuery] = useState('')
  const [searchParams, setSearchParams] = useState<{
    query: string
    region: string | null
    source_types: SourceType[] | null
    short: boolean
    spellcheck: boolean
  } | null>(null)
  const [sortMode, setSortMode] = useState<SortMode>('sources')
  const [selectedRegion, setSelectedRegion] = useState<RegionName>(ALL_REGIONS)
  const [extendedRunetSearch, setExtendedRunetSearch] = useState(false)
  const { jobInfo, startSearch, isSearching, error } = useSearchJob({ jobId, setJobId })
  const apiSourceGroups = jobInfo?.sources.map(mapSearchSourceToGroup)
  const visibleGroups = apiSourceGroups ?? []
  const typofixSuggestions = jobInfo?.typofix_suggestions ?? []
  const typofixSuggestionBySource = new Map(
    typofixSuggestions.map(({ source, suggestion }) => [source, suggestion] as const)
  )
  const correctedQuery =
    typofixSuggestionBySource.get(SourceType.ozon) ??
    typofixSuggestions[0]?.suggestion ??
    null
  const originalQuery =
    jobInfo?.original_params.query ?? searchParams?.query ?? query.trim() ?? ''
  const executedSearchQuery = correctedQuery ?? originalQuery
  const hasTypofixSuggestions =
    Boolean(correctedQuery) && correctedQuery !== originalQuery

  const getSourceQueryLabel = (sourceType: SourceType) => {
    const sourceQuery = typofixSuggestionBySource.get(sourceType) ?? executedSearchQuery
    return `Результат запроса по «${sourceQuery}»`
  }

  const plannedSources = plannedSourceTypes(
    searchParams?.source_types ?? jobInfo?.original_params.source_types
  )
  const marketplaceSourceTypes = plannedSources.filter(
    (sourceType) => sourceType !== SourceType.runet
  )
  const runetGroups = visibleGroups.filter((group) => group.sourceType === SourceType.runet)
  const sortedMarketplaceSourceTypes = [...marketplaceSourceTypes].sort((leftType, rightType) => {
    const leftPlanIndex = plannedSources.indexOf(leftType)
    const rightPlanIndex = plannedSources.indexOf(rightType)
    const leftStatus =
      leftPlanIndex === -1 ? undefined : jobInfo?.sources_statuses[leftPlanIndex]
    const rightStatus =
      rightPlanIndex === -1 ? undefined : jobInfo?.sources_statuses[rightPlanIndex]
    const leftGroups = visibleGroups.filter((group) => group.sourceType === leftType)
    const rightGroups = visibleGroups.filter((group) => group.sourceType === rightType)
    const leftPending =
      isSearching &&
      (leftStatus === undefined || leftStatus === SourceStatus.PENDING) &&
      leftGroups.length === 0
    const rightPending =
      isSearching &&
      (rightStatus === undefined || rightStatus === SourceStatus.PENDING) &&
      rightGroups.length === 0
    const leftSource = jobInfo?.sources.find((source) => source.source_type === leftType)
    const rightSource = jobInfo?.sources.find((source) => source.source_type === rightType)
    const leftSourceOrder =
      jobInfo?.sources.findIndex((source) => source.source_type === leftType) ?? -1
    const rightSourceOrder =
      jobInfo?.sources.findIndex((source) => source.source_type === rightType) ?? -1

    return compareByParseReadiness(
      {
        isReady: !leftPending,
        readyAt: getSearchSourceReadyAt(
          leftSource,
          leftSourceOrder >= 0 ? leftSourceOrder : Number.MAX_SAFE_INTEGER - 1
        ),
        tieBreaker: leftPlanIndex >= 0 ? leftPlanIndex : 0
      },
      {
        isReady: !rightPending,
        readyAt: getSearchSourceReadyAt(
          rightSource,
          rightSourceOrder >= 0 ? rightSourceOrder : Number.MAX_SAFE_INTEGER - 1
        ),
        tieBreaker: rightPlanIndex >= 0 ? rightPlanIndex : 0
      }
    )
  })
  const visibleRunetGroups = runetGroups
    .filter((group) => group.isParsing || group.products.length > 0)
    .sort((left, right) => {
      const leftSource = jobInfo?.sources.find((source) => source.source_url === left.sourceUrl)
      const rightSource = jobInfo?.sources.find((source) => source.source_url === right.sourceUrl)
      const leftSourceOrder =
        jobInfo?.sources.findIndex((source) => source.source_url === left.sourceUrl) ?? -1
      const rightSourceOrder =
        jobInfo?.sources.findIndex((source) => source.source_url === right.sourceUrl) ?? -1

      return compareByParseReadiness(
        {
          isReady: !left.isParsing,
          readyAt: getSearchSourceReadyAt(
            leftSource,
            leftSourceOrder >= 0 ? leftSourceOrder : Number.MAX_SAFE_INTEGER - 1
          ),
          tieBreaker: leftSourceOrder >= 0 ? leftSourceOrder : 0
        },
        {
          isReady: !right.isParsing,
          readyAt: getSearchSourceReadyAt(
            rightSource,
            rightSourceOrder >= 0 ? rightSourceOrder : Number.MAX_SAFE_INTEGER - 1
          ),
          tieBreaker: rightSourceOrder >= 0 ? rightSourceOrder : 0
        }
      )
    })
  const runetPlanIndex = plannedSources.indexOf(SourceType.runet)
  const isRunetSearchPlanned = runetPlanIndex !== -1
  const isRunetSourcePending =
    isRunetSearchPlanned &&
    isSearching &&
    jobInfo?.sources_statuses[runetPlanIndex] === SourceStatus.PENDING
  const readyGroups = visibleGroups.filter((group) => !group.isParsing)

  const totalProducts = readyGroups.reduce((sum, group) => sum + group.products.length, 0)
  const allProducts: SearchResultProduct[] = readyGroups.flatMap((group) =>
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
          if (left.product.relevant !== right.product.relevant) {
            return left.product.relevant === false ? 1 : -1
          }
          if (left.parsedPrice === null && right.parsedPrice === null) return 0
          if (left.parsedPrice === null) return 1
          if (right.parsedPrice === null) return -1

          return sortMode === 'price-asc'
            ? left.parsedPrice - right.parsedPrice
            : right.parsedPrice - left.parsedPrice
        })

  const allPrices = readyGroups.flatMap((group) =>
    group.products.map((p) => parsePrice(p.price)).filter((p): p is number => p !== null)
  )
  const averagePrice =
    allPrices.length > 0 ? allPrices.reduce((sum, p) => sum + p, 0) / allPrices.length : null

  useEffect(() => {
    if (jobId === undefined) {
      hydratedJobIdRef.current = undefined
    }
  }, [jobId])

  useEffect(() => {
    if (!jobInfo || jobInfo.job_id === hydratedJobIdRef.current) return

    hydratedJobIdRef.current = jobInfo.job_id
    const params = jobInfo.original_params
    setQuery(params.query)
    setSelectedRegion(regionNameByCapital(params.region))
    setExtendedRunetSearch(params.source_types === null)
    setSearchParams({
      query: params.query,
      region: params.region ?? null,
      source_types: params.source_types ?? null,
      short: params.short,
      spellcheck: params.spellcheck
    })
  }, [jobInfo])

  const runSearch = (
    nextQuery: string,
    options: { spellcheck?: boolean } = {}
  ) => {
    const spellcheck = options.spellcheck ?? true
    const region = selectedRegion === ALL_REGIONS ? null : regionCapitalByName[selectedRegion]
    const source_types = sourceTypesForRunetSearch(extendedRunetSearch)

    setSearchParams({
      query: nextQuery,
      region,
      source_types,
      short: false,
      spellcheck
    })
    startSearch({
      query: nextQuery,
      region,
      source_types,
      short: false,
      spellcheck
    })
  }

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedQuery = query.trim()

    if (!trimmedQuery) return

    runSearch(trimmedQuery)
  }

  const handleRevertTypofix = () => {
    setQuery(originalQuery)
    runSearch(originalQuery, { spellcheck: false })
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
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="search-query">
              Строка поиска
            </label>
            <SpellcheckSearchInput
              disabled={isSearching}
              id="search-query"
              inputRef={searchInputRef}
              onCaretChange={() => {}}
              onChange={setQuery}
              placeholder="Введите товар или характеристику"
              value={query}
            />
            {hasTypofixSuggestions && correctedQuery && !isSearching ? (
              <TypofixNotice
                correctedQuery={correctedQuery}
                onRevert={handleRevertTypofix}
                originalQuery={originalQuery}
              />
            ) : null}
          </div>

          <RegionDropdown onSelect={setSelectedRegion} selectedRegion={selectedRegion} />

          <div className="flex flex-col gap-2">
            <span className="invisible text-sm font-medium">Search</span>
            <Button className="h-11 w-full gap-2 px-4 text-sm" disabled={isSearching} type="submit">
              {isSearching ? (
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Search aria-hidden="true" className="size-4" />
              )}
              {isSearching ? 'Ищем...' : 'Найти'}
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

        <section
          aria-busy={isSearching}
          aria-label="Источники товаров"
          className="flex flex-col gap-4"
        >
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">Основные источники</h2>
              <p className="text-sm text-slate-600">Регион: {selectedRegion}</p>
            </div>
            <div className="flex flex-col items-end gap-1">
              {averagePrice !== null && !isSearching && (
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
                {isSearching ? 'Идёт поиск...' : `Найдено товаров: ${totalProducts}`}
              </p>
            </div>
          </div>

          {totalProducts > 0 ? (
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

          {sortMode === 'sources' && (searchParams || jobId !== undefined) ? (
            <>
              {sortedMarketplaceSourceTypes.flatMap((sourceType) => {
                const planIndex = plannedSources.indexOf(sourceType)
                const sourceStatus =
                  planIndex === -1 ? undefined : jobInfo?.sources_statuses[planIndex]
                const groups = visibleGroups.filter((group) => group.sourceType === sourceType)
                const isMarketplacePending =
                  isSearching &&
                  (sourceStatus === undefined || sourceStatus === SourceStatus.PENDING) &&
                  groups.length === 0

                if (isMarketplacePending) {
                  return [<ProductSourceSkeleton key={sourceType} />]
                }

                if (groups.length === 0) return []

                return groups
                  .filter((group) => group.isParsing || group.products.length > 0)
                  .map((group) => (
                  <ProductSourceDetails
                    group={group}
                    key={`${group.sourceType}-${group.title}`}
                    queryResultLabel={getSourceQueryLabel(group.sourceType)}
                  />
                ))
              })}

              {isRunetSourcePending || visibleRunetGroups.length > 0 ? (
                <div className="flex flex-col gap-4">
                  <h3 className="text-lg font-semibold text-slate-950">Рунет</h3>
                  {visibleRunetGroups.length === 0 && isRunetSourcePending ? (
                    <ProductSourceSkeleton />
                  ) : null}
                  {visibleRunetGroups.map((group) => (
                    <ProductSourceDetails
                      group={group}
                      isParsing={group.isParsing}
                      key={`runet-${group.sourceUrl}`}
                      queryResultLabel={
                        group.isParsing ? null : getSourceQueryLabel(SourceType.runet)
                      }
                    />
                  ))}
                </div>
              ) : null}
            </>
          ) : null}

          {sortMode !== 'sources' ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {sortedProducts.map((item, index) => (
                <div
                  className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
                  key={`${item.sourceType}-${item.product.product_link ?? item.product.name}-${index}`}
                >
                  <div
                    className="flex items-center justify-between gap-3 border-b bg-slate-50 px-4 py-3"
                    style={getMarketplaceTheme(item.sourceType).summaryStyle}
                  >
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
                      className="shrink-0 text-sm font-medium text-slate-900 transition hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
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
