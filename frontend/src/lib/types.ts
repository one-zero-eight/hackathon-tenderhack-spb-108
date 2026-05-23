import type { SearchSourceSource_type } from '@/api/openapi.gen'

export type Product = {
  title: string
  image: string | null
  characteristics: string[]
  productLink?: string | null
  price?: string | null
  rating?: string | null
  reviews?: string | null
}

export type MarketplaceGroup = {
  sourceType: SearchSourceSource_type
  title: string
  logoUrl: string
  sourceUrl: string
  products: Product[]
}
