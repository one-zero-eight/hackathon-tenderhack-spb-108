import type { QueryClient } from '@tanstack/react-query'

import type { SchemaSearchResults } from '@/api/openapi.gen'

const LAST_SEARCH_STORAGE_KEY = 'marketplace-search:last-result:v1'
const ALL_REGION_KEY = '__all_regions__'

export function normalizeRegionKey(region: string | null) {
  return region ?? ALL_REGION_KEY
}

export const marketplaceSearchKeys = {
  all: ['marketplace-search'] as const,
  latestResult: () => [...marketplaceSearchKeys.all, 'latest-result'] as const,
  result: (query: string, region: string | null) =>
    [...marketplaceSearchKeys.all, 'result', query, normalizeRegionKey(region)] as const
}

export function persistLatestSearchResult(result: SchemaSearchResults) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(LAST_SEARCH_STORAGE_KEY, JSON.stringify(result))
}

export function restoreLatestSearchResult(queryClient: QueryClient) {
  if (typeof window === 'undefined') {
    return
  }

  const raw = window.localStorage.getItem(LAST_SEARCH_STORAGE_KEY)
  if (!raw) {
    return
  }

  try {
    const parsed = JSON.parse(raw) as SchemaSearchResults
    setSearchResultCache(queryClient, parsed)
  } catch {
    window.localStorage.removeItem(LAST_SEARCH_STORAGE_KEY)
  }
}

export function setSearchResultCache(queryClient: QueryClient, result: SchemaSearchResults) {
  const { query, region } = result.original_params

  queryClient.setQueryData(marketplaceSearchKeys.latestResult(), result)
  queryClient.setQueryData(marketplaceSearchKeys.result(query, region), result)
}
