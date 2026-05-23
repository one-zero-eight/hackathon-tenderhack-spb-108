import { ProductSourceDetails } from '@/components/ProductSourceDetails'
import { RegionDropdown } from '@/components/RegionDropdown'
import { mapSearchSourceToGroup } from '@/lib/mapping'
import { ALL_REGIONS, regionCapitalByName, type RegionName } from '@/lib/regions'
import { createFileRoute } from '@tanstack/react-router'
import { LoaderCircle, Search } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import exampleSearchResultsRaw from '../../example.json?raw'
import { $api } from '../api'
import { type SchemaSearchResults, SourceType } from '../api/openapi.gen'
import { Button } from '../components/ui/button'

export const Route = createFileRoute('/')({ component: Home })

const MARKETPLACE_SOURCE_TYPES = [
  SourceType.yandex_market,
  SourceType.wildberries,
  SourceType.ozon
] as const

function sourceTypesForRunetSearch(extendedRunetSearch: boolean): SourceType[] | null {
  return extendedRunetSearch ? null : [...MARKETPLACE_SOURCE_TYPES]
}

type TypofixSuggestion = {
  source: SourceType
  suggestion: string
}

type SearchResultsWithTypofix = SchemaSearchResults & {
  typofix_suggestions?: TypofixSuggestion[]
}

function Home() {
  const searchInputRef = useRef<HTMLInputElement>(null)
  const [searchParams, setSearchParams] = useState<{
    query: string
    region: string | null
    source_types: SourceType[] | null
  } | null>(null)
  const [selectedRegion, setSelectedRegion] = useState<RegionName>(ALL_REGIONS)
  const [extendedRunetSearch, setExtendedRunetSearch] = useState(false)
  const {
    data: searchResults,
    error,
    isFetching
  } = $api.useQuery(
    'post',
    '/search/search',
    {
      body: searchParams ?? {
        query: '',
        region: null,
        source_types: sourceTypesForRunetSearch(extendedRunetSearch)
      }
    },
    {
      enabled: searchParams !== null
    }
  )
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
  const isSearchDisabled = isFetching

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const query = searchInputRef.current?.value.trim() ?? ''

    if (!query) return

    setSearchParams({
      query,
      region: selectedRegion === ALL_REGIONS ? null : regionCapitalByName[selectedRegion],
      source_types: sourceTypesForRunetSearch(extendedRunetSearch)
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
          className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[minmax(0,1fr)_320px_auto]"
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

          <div className="flex flex-col justify-end gap-3">
            <label className="flex cursor-pointer items-center justify-between gap-3">
              <span className="text-sm font-medium text-slate-700">Расширенный поиск по Рунету</span>
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
            <Button
              className="h-11 w-full gap-2 px-4 text-sm md:min-w-32"
              disabled={isSearchDisabled}
              type="submit"
            >
              {isFetching ? (
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Search aria-hidden="true" className="size-4" />
              )}
              {isFetching ? 'Ищем...' : 'Найти'}
            </Button>
          </div>
        </form>

        {hasTypofixSuggestions ? (
          <p className="text-sm text-slate-600">
            Возможно, вы имели в виду{' '}
            {uniqueTypofixSuggestions.map((suggestion) => `"${suggestion}"`).join(', ')}
          </p>
        ) : null}

        <section className="flex flex-col gap-4" aria-label="Источники товаров">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">Основные источники</h2>
              <p className="text-sm text-slate-600">Регион: {selectedRegion}</p>
            </div>
            <p className="text-sm text-slate-500">
              {isFetching ? 'Идёт поиск...' : `Найдено товаров: ${totalProducts}`}
            </p>
          </div>

          {error ? (
            <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              Не удалось выполнить поиск. Попробуйте ещё раз.
            </p>
          ) : null}

          {visibleGroups.map((group) => (
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
          ))}
        </section>
      </section>
    </main>
  )
}
