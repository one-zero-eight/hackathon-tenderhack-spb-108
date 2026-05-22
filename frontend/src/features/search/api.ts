import { apiFetch } from '@/api'
import type { SchemaSearchResults } from '@/api/openapi.gen'

export type MarketplaceSearchParams = {
  query: string
  region: string | null
}

export class MarketplaceSearchError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'MarketplaceSearchError'
  }
}

function formatSearchError(error: unknown) {
  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = error.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }

  return 'Не удалось выполнить поиск. Попробуйте еще раз.'
}

export async function searchMarketplaces(
  params: MarketplaceSearchParams
): Promise<SchemaSearchResults> {
  try {
    const { data, error } = await apiFetch.POST('/search/search', {
      body: params
    })

    if (error || !data) {
      throw new MarketplaceSearchError(formatSearchError(error))
    }

    return data
  } catch (error) {
    if (error instanceof MarketplaceSearchError) {
      throw error
    }

    throw new MarketplaceSearchError('Не удалось связаться с сервером. Попробуйте еще раз.')
  }
}
