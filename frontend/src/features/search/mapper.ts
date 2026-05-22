import type { SchemaSearchResult, SchemaSearchSource } from '@/api/openapi.gen'
import type { MarketplaceGroup } from '@/lib/mock'

function prettifyCharacteristicKey(key: string) {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/^\w/, (letter) => letter.toUpperCase())
}

function buildMarketplaceLogo(source: SchemaSearchSource) {
  if (source.source_favicon_url) {
    return source.source_favicon_url
  }

  try {
    const hostname = new URL(source.source_url).hostname
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=64`
  } catch {
    return null
  }
}

function mapResultToCharacteristics(result: SchemaSearchResult) {
  const entries = Object.entries(result.characteristics ?? {})

  if (entries.length === 0) {
    return []
  }

  return entries.map(([key, value]) => `${prettifyCharacteristicKey(key)}: ${value}`)
}

export function mapSourceToGroup(source: SchemaSearchSource): MarketplaceGroup {
  return {
    title: source.source_title,
    logoUrl: buildMarketplaceLogo(source),
    sourceUrl: source.source_url,
    products: source.results.map((result) => ({
      title: result.name,
      image: result.image_link,
      characteristics: mapResultToCharacteristics(result),
      price: result.price,
      url: null
    }))
  }
}
