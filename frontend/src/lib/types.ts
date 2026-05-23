import type { SchemaSearchResult, SchemaSearchResults, SourceType } from '@/api/openapi.gen'

export type MarketplaceGroup = {
  sourceType: SourceType
  title: string
  logoUrl: string
  sourceUrl: string
  products: SchemaSearchResult[]
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
  product: SchemaSearchResult
  sourceType: SourceType
  sourceTitle: string
  sourceUrl: string
  sourceLogoUrl: string
  parsedPrice: number | null
}
