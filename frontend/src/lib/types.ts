import type { SchemaSearchResults, SourceType } from '@/api/openapi.gen'

export type Product = {
  title: string
  image: string | null
  images: string[]
  characteristics: string[]
  productLink?: string | null
  price?: string | null
  rating?: string | null
  reviews?: string | null
}

export type MarketplaceGroup = {
  sourceType: SourceType
  title: string
  logoUrl: string
  sourceUrl: string
  products: Product[]
}

export type TypofixSuggestion = {
  source: SourceType
  suggestion: string
}

export type SearchResultsWithTypofix = SchemaSearchResults & {
  typofix_suggestions?: TypofixSuggestion[]
}

export type SortMode = 'sources' | 'price-asc' | 'price-desc'

export type SearchResultProduct = {
  product: Product
  sourceType: SourceType
  sourceTitle: string
  sourceUrl: string
  sourceLogoUrl: string
  parsedPrice: number | null
}
