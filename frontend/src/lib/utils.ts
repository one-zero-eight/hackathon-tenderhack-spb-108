import { SourceType, SpellcheckLanguage, type SchemaSearchResult, type SchemaSearchSource } from '@/api/openapi.gen'
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function parsePrice(priceStr: string | null | undefined): number | null {
  if (!priceStr) return null
  const cleanStr = priceStr.replace(/[\s  ]/g, '')
  const match = cleanStr.match(/\d+([.,]\d+)?/)
  if (!match) return null
  return parseFloat(match[0].replace(',', '.'))
}

export function sortProductsByRelevance(products: SchemaSearchResult[]): SchemaSearchResult[] {
  const relevant: SchemaSearchResult[] = []
  const irrelevant: SchemaSearchResult[] = []

  for (const product of products) {
    if (product.relevant === false) {
      irrelevant.push(product)
    } else {
      relevant.push(product)
    }
  }

  return [...relevant, ...irrelevant]
}

export const MARKETPLACE_SOURCE_TYPES = [
  SourceType.yandex_market,
  SourceType.wildberries,
  SourceType.ozon
] as const

export const ALL_SOURCE_TYPES = [
  SourceType.yandex_market,
  SourceType.wildberries,
  SourceType.ozon,
  SourceType.runet
] as const

export function sourceTypesForRunetSearch(extendedRunetSearch: boolean): SourceType[] | null {
  return extendedRunetSearch ? null : [...MARKETPLACE_SOURCE_TYPES]
}

export function plannedSourceTypes(sourceTypes: SourceType[] | null | undefined): SourceType[] {
  return sourceTypes?.length ? [...sourceTypes] : [...ALL_SOURCE_TYPES]
}

export function getSearchSourceReadyAt(
  source: Pick<SchemaSearchSource, 'timing'> | undefined,
  fallbackOrder = Number.MAX_SAFE_INTEGER - 1
): number {
  const endedAt = source?.timing?.ended_at
  if (endedAt) {
    const timestamp = Date.parse(endedAt)
    if (!Number.isNaN(timestamp)) return timestamp
  }

  return fallbackOrder
}

export function compareByParseReadiness(
  left: { isReady: boolean; readyAt: number; tieBreaker: number },
  right: { isReady: boolean; readyAt: number; tieBreaker: number }
): number {
  if (left.isReady !== right.isReady) {
    return left.isReady ? -1 : 1
  }

  if (left.isReady && right.isReady && left.readyAt !== right.readyAt) {
    return left.readyAt - right.readyAt
  }

  return left.tieBreaker - right.tieBreaker
}

export type WordRange = {
  word: string
  start: number
  end: number
}

export type QueryPart =
  | { type: 'space'; value: string; start: number }
  | { type: 'word'; value: string; index: number; start: number; end: number }

export function splitQueryParts(text: string): QueryPart[] {
  const parts: QueryPart[] = []
  let wordIndex = 0
  let offset = 0

  for (const segment of text.split(/(\s+)/)) {
    if (!segment) continue
    if (/^\s+$/.test(segment)) {
      parts.push({ type: 'space', value: segment, start: offset })
      offset += segment.length
      continue
    }
    parts.push({
      type: 'word',
      value: segment,
      index: wordIndex,
      start: offset,
      end: offset + segment.length
    })
    wordIndex += 1
    offset += segment.length
  }

  return parts
}

export function getChangedWordIndexes(original: string, corrected: string): Set<number> {
  const originalWords = original.trim().split(/\s+/)
  const correctedWords = corrected.trim().split(/\s+/)
  const changed = new Set<number>()
  const maxLength = Math.max(originalWords.length, correctedWords.length)

  for (let index = 0; index < maxLength; index += 1) {
    const left = originalWords[index] ?? ''
    const right = correctedWords[index] ?? ''
    if (left.toLowerCase() !== right.toLowerCase()) {
      changed.add(index)
    }
  }

  return changed
}

export function getSpellcheckableWords(text: string): WordRange[] {
  const words: WordRange[] = []
  let offset = 0

  for (const part of text.split(/(\s+)/)) {
    if (!part || /^\s+$/.test(part)) {
      offset += part.length
      continue
    }

    if (part.length > 2 && detectSpellcheckLanguage(part)) {
      words.push({
        word: part,
        start: offset,
        end: offset + part.length
      })
    }

    offset += part.length
  }

  return words
}

export function getWordAtCaret(text: string, caretPosition: number): WordRange | null {
  const safeCaretPosition = Math.max(0, Math.min(caretPosition, text.length))

  let start = safeCaretPosition
  let end = safeCaretPosition

  while (start > 0 && text[start - 1] !== ' ') {
    start -= 1
  }

  while (end < text.length && text[end] !== ' ') {
    end += 1
  }

  const word = text.slice(start, end).trim()
  if (!word) return null

  return {
    word,
    start,
    end
  }
}

export function detectSpellcheckLanguage(word: string): SpellcheckLanguage | null {
  const lastChar = word.at(-1)
  if (!lastChar) return null

  if (/[0-9]/.test(lastChar)) {
    return null
  }

  if (/[A-Za-z]/.test(lastChar)) {
    return SpellcheckLanguage.en_US
  }

  if (/[А-Яа-яЁё]/u.test(lastChar)) {
    return SpellcheckLanguage.ru_RU
  }

  return null
}
