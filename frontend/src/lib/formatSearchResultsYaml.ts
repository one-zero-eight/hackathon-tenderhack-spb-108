import { SourceType, type SchemaSearchResult } from '@/api/openapi.gen'
import type { MarketplaceGroup } from '@/lib/types'

const PRODUCTS_LIMIT = 5
const CHARACTERISTICS_LIMIT = 5

const MARKETPLACE_SECTIONS = [
  { sourceType: SourceType.ozon, key: 'ozon', linkLabel: 'ozon' },
  { sourceType: SourceType.yandex_market, key: 'яндекс_маркет', linkLabel: 'яндекс маркет' },
  { sourceType: SourceType.wildberries, key: 'wildberries', linkLabel: 'wildberries' }
] as const

function yamlScalar(value: string): string {
  return JSON.stringify(value)
}

function yamlKey(key: string): string {
  return /^[a-zA-Z_][a-zA-Z0-9_-]*$/.test(key) ? key : yamlScalar(key)
}

function formatCharacteristics(
  characteristics: SchemaSearchResult['characteristics'],
  indent: number
): string[] {
  const entries = Object.entries(characteristics ?? {}).slice(0, CHARACTERISTICS_LIMIT)
  if (entries.length === 0) return []

  const pad = '  '.repeat(indent)
  const childPad = '  '.repeat(indent + 1)

  return [
    `${pad}характеристики:`,
    ...entries.map(([name, value]) => `${childPad}${yamlKey(name)}: ${yamlScalar(value)}`)
  ]
}

function formatProduct(
  product: SchemaSearchResult,
  index: number,
  linkLabel: string,
  indent: number
): string[] {
  const pad = '  '.repeat(indent)
  const lines = [`${pad}- название: ${yamlScalar(product.name)}`, ...formatCharacteristics(product.characteristics, indent + 1)]

  lines.push(`${pad}  метка_ссылки: ${yamlScalar(`Ссылка на ${linkLabel} ${index + 1}`)}`)
  if (product.product_link) {
    lines.push(`${pad}  ссылка: ${yamlScalar(product.product_link)}`)
  }

  return lines
}

export function formatSearchResultsYaml(query: string, groups: MarketplaceGroup[]): string {
  const lines = [`введенный_запрос: ${yamlScalar(query)}`, '']

  for (const { sourceType, key, linkLabel } of MARKETPLACE_SECTIONS) {
    const products = groups
      .filter((group) => group.sourceType === sourceType && !group.isParsing)
      .flatMap((group) => group.products)
      .slice(0, PRODUCTS_LIMIT)

    lines.push(`${key}:`)

    if (products.length === 0) {
      lines.push('  []')
    } else {
      for (const [index, product] of products.entries()) {
        lines.push(...formatProduct(product, index, linkLabel, 1))
      }
    }

    lines.push('')
  }

  return `${lines.join('\n').trimEnd()}\n`
}
