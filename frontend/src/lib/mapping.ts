import type { SchemaSearchSource } from '@/api/openapi.gen'
import type { MarketplaceGroup } from '@/lib/types'

export function mapSearchSourceToGroup(source: SchemaSearchSource): MarketplaceGroup {
  return {
    sourceType: source.source_type,
    title: source.source_title,
    logoUrl:
      source.source_favicon_url ??
      `https://www.google.com/s2/favicons?domain=${source.source_url}&sz=64`,
    sourceUrl: source.source_url,
    products: source.results.map((result) => ({
      title: result.name,
      image: result.image_link ?? null,
      characteristics: Object.entries(result.characteristics ?? {}).map(
        ([name, value]) => `${name}: ${value}`
      ),
      productLink: result.product_link,
      price: result.price,
      rating: result.rating,
      reviews: result.reviews
    }))
  }
}
