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
  title: string
  logoUrl: string
  sourceUrl: string
  products: Product[]
}
