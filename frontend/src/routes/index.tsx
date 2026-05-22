import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { ChevronDown, ExternalLink, ImageOff, LoaderCircle, Search, Store } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import type { SchemaSearchResults } from '@/api/openapi.gen'
import { MarketplaceSearchError, searchMarketplaces } from '@/features/search/api'
import {
  marketplaceSearchKeys,
  persistLatestSearchResult,
  setSearchResultCache
} from '@/features/search/cache'
import { mapSourceToGroup } from '@/features/search/mapper'
import { marketplaceGroups, otherSourceGroups, regions, type MarketplaceGroup } from '@/lib/mock'

export const Route = createFileRoute('/')({ component: Home })

const OTHER_SOURCES_STEP = 10
const ALL_REGIONS_LABEL = regions[0] ?? 'Все регионы'

function RegionDropdown({
  selectedRegion,
  onSelect
}: {
  selectedRegion: string
  onSelect: (region: string) => void
}) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="relative flex flex-col gap-2">
      <span className="text-sm font-medium text-slate-700">Выбор региона</span>
      <button
        aria-expanded={isOpen}
        className="flex h-11 w-full items-center justify-between gap-3 rounded-md border border-slate-300 bg-white px-3 text-left text-sm outline-none transition focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
        onClick={() => setIsOpen((current) => !current)}
        type="button"
      >
        <span className="truncate">{selectedRegion}</span>
        <ChevronDown
          aria-hidden="true"
          className={`size-4 shrink-0 text-slate-500 transition ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen ? (
        <div className="absolute left-0 right-0 top-full z-20 mt-2 max-h-72 overflow-y-auto rounded-md border border-slate-200 bg-white py-1 shadow-lg">
          {regions.map((region, index) => (
            <button
              className={`block w-full px-3 py-2 text-left text-sm transition hover:bg-slate-100 ${
                region === selectedRegion ? 'font-medium text-slate-950' : 'text-slate-700'
              } ${index === 0 ? 'sticky top-0 z-10 border-b border-slate-200 bg-white' : ''}`}
              key={region}
              onClick={() => {
                onSelect(region)
                setIsOpen(false)
              }}
              type="button"
            >
              {region}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function ProductSourceDetails({ group }: { group: MarketplaceGroup }) {
  return (
    <details className="group rounded-lg border border-slate-200 bg-white shadow-sm" open>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-4 marker:hidden">
        <span className="flex min-w-0 items-center gap-3">
          {group.logoUrl ? (
            <img
              alt=""
              className="size-10 shrink-0 rounded-md border border-slate-200 bg-white object-contain p-1"
              loading="lazy"
              src={group.logoUrl}
            />
          ) : (
            <span className="flex size-10 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-500">
              <Store aria-hidden="true" className="size-5" />
            </span>
          )}

          <span className="min-w-0">
            <span className="block truncate text-base font-semibold text-slate-950">
              {group.title}
            </span>
            <a
              className="mt-1 inline-flex items-center gap-1 text-sm text-slate-500 transition hover:text-slate-900"
              href={group.sourceUrl}
              onClick={(event) => event.stopPropagation()}
              rel="noreferrer"
              target="_blank"
            >
              Перейти на маркетплейс
              <ExternalLink aria-hidden="true" className="size-3.5" />
            </a>
          </span>
        </span>
        <span className="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600">
          {group.products.length}
        </span>
      </summary>

      <div className="border-t border-slate-200 p-4">
        {group.products.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {group.products.map((product) => {
              const productLink = product.url ?? group.sourceUrl
              const hasDirectLink = Boolean(product.url)

              return (
                <article
                  className="flex h-full flex-col overflow-hidden rounded-lg border border-slate-200 bg-white"
                  key={`${group.title}-${product.title}`}
                >
                  {product.image ? (
                    <img
                      alt={product.title}
                      className="h-44 w-full object-cover"
                      loading="lazy"
                      src={product.image}
                    />
                  ) : (
                    <div className="flex h-44 w-full items-center justify-center bg-slate-100 text-slate-400">
                      <div className="flex flex-col items-center gap-2">
                        <ImageOff aria-hidden="true" className="size-8" />
                        <span className="text-sm">Нет изображения</span>
                      </div>
                    </div>
                  )}

                  <div className="flex flex-1 flex-col gap-3 p-4">
                    <div className="space-y-2">
                      <h3 className="text-base font-semibold leading-6 text-slate-950">
                        {product.title}
                      </h3>

                      {product.price ? (
                        <p className="text-lg font-semibold text-slate-950">{product.price} ₽</p>
                      ) : (
                        <p className="text-sm text-slate-500">Цена не указана</p>
                      )}
                    </div>

                    {product.characteristics.length > 0 ? (
                      <ul className="space-y-1 text-sm text-slate-600">
                        {product.characteristics.map((characteristic) => (
                          <li
                            className="border-l border-slate-200 pl-3 leading-5"
                            key={characteristic}
                          >
                            {characteristic}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-slate-500">Характеристики не указаны</p>
                    )}

                    <a
                      className="mt-auto inline-flex items-center gap-2 text-sm font-medium text-slate-700 transition hover:text-slate-950"
                      href={productLink}
                      rel="noreferrer"
                      target="_blank"
                    >
                      {hasDirectLink ? 'Открыть товар' : 'Открыть маркетплейс'}
                      <ExternalLink aria-hidden="true" className="size-4" />
                    </a>
                  </div>
                </article>
              )
            })}
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

function Home() {
  const queryClient = useQueryClient()
  const initialLatestSearchResult =
    queryClient.getQueryData<SchemaSearchResults | null>(marketplaceSearchKeys.latestResult()) ??
    null

  const [searchQuery, setSearchQuery] = useState(
    initialLatestSearchResult?.original_params.query ?? ''
  )
  const [selectedRegion, setSelectedRegion] = useState(
    initialLatestSearchResult?.original_params.region ?? ALL_REGIONS_LABEL
  )
  const [visibleOtherSources, setVisibleOtherSources] = useState(OTHER_SOURCES_STEP)

  const { data: latestSearchResult } = useQuery<SchemaSearchResults | null>({
    queryKey: marketplaceSearchKeys.latestResult(),
    queryFn: async () => null,
    initialData: initialLatestSearchResult,
    staleTime: Infinity,
    gcTime: Infinity
  })

  const searchMutation = useMutation({
    mutationFn: searchMarketplaces,
    onSuccess: (result) => {
      setSearchResultCache(queryClient, result)
      persistLatestSearchResult(result)
    }
  })

  const isShowingMockData = !latestSearchResult
  const searchGroups = latestSearchResult?.sources.map(mapSourceToGroup) ?? []
  const visibleOtherSourceGroups = otherSourceGroups.slice(0, visibleOtherSources)
  const hiddenOtherSourcesCount = Math.max(otherSourceGroups.length - visibleOtherSources, 0)
  const totalProducts = (
    isShowingMockData ? [...marketplaceGroups, ...otherSourceGroups] : searchGroups
  ).reduce((sum, group) => sum + group.products.length, 0)
  const displayedRegion = latestSearchResult?.original_params.region ?? selectedRegion
  const displayedQuery = latestSearchResult?.original_params.query ?? null

  async function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const trimmedQuery = searchQuery.trim()
    if (!trimmedQuery) {
      return
    }

    const region = selectedRegion === ALL_REGIONS_LABEL ? null : selectedRegion

    await searchMutation.mutateAsync({
      query: trimmedQuery,
      region
    })
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-3">
          <div className="max-w-3xl">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
              Поиск товаров по Рунету
            </h1>
            <p className="mt-2 text-sm text-slate-600">
              До первого поиска показываем моковые данные, после запроса отображаем ответ backend.
            </p>
          </div>
        </header>

        <form
          aria-label="Фильтры каталога"
          className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[minmax(0,1fr)_320px_160px]"
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
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Введите товар или характеристику"
                type="search"
                value={searchQuery}
              />
            </span>
          </label>

          <RegionDropdown onSelect={setSelectedRegion} selectedRegion={selectedRegion} />

          <button
            className="inline-flex h-11 items-center justify-center gap-2 self-end rounded-md bg-slate-950 px-4 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            disabled={searchMutation.isPending || searchQuery.trim().length === 0}
            type="submit"
          >
            {searchMutation.isPending ? (
              <>
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
                Ищем
              </>
            ) : (
              <>
                <Search aria-hidden="true" className="size-4" />
                Найти
              </>
            )}
          </button>
        </form>

        {searchMutation.isError ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {searchMutation.error instanceof MarketplaceSearchError
              ? searchMutation.error.message
              : 'Не удалось выполнить поиск. Попробуйте еще раз.'}
          </div>
        ) : null}

        <section aria-label="Источники товаров" className="flex flex-col gap-4">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">
                {isShowingMockData ? 'Основные источники' : 'Результаты поиска'}
              </h2>
              <p className="text-sm text-slate-600">
                Регион: {displayedRegion ?? ALL_REGIONS_LABEL}
              </p>
              {displayedQuery ? (
                <p className="text-sm text-slate-600">Запрос: {displayedQuery}</p>
              ) : (
                <p className="text-sm text-slate-600">Пока показаны демонстрационные данные</p>
              )}
            </div>
            <p className="text-sm text-slate-500">Найдено товаров: {totalProducts}</p>
          </div>

          {isShowingMockData ? (
            <>
              {marketplaceGroups.map((group) => (
                <ProductSourceDetails group={group} key={group.title} />
              ))}

              <h2 className="pt-3 text-xl font-semibold text-slate-950">Другие источники</h2>

              {visibleOtherSourceGroups.map((group) => (
                <ProductSourceDetails group={group} key={group.title} />
              ))}

              {hiddenOtherSourcesCount > 0 ? (
                <button
                  className="self-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 shadow-sm transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
                  onClick={() => setVisibleOtherSources((current) => current + OTHER_SOURCES_STEP)}
                  type="button"
                >
                  Показать ещё ({hiddenOtherSourcesCount} источников)
                </button>
              ) : null}
            </>
          ) : (
            searchGroups.map((group) => <ProductSourceDetails group={group} key={group.title} />)
          )}
        </section>
      </section>
    </main>
  )
}
