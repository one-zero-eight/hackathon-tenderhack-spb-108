import { SourceType, SpellcheckLanguage } from '@/api/openapi.gen'
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

export const MARKETPLACE_SOURCE_TYPES = [
  SourceType.yandex_market,
  SourceType.wildberries,
  SourceType.ozon
] as const

export function sourceTypesForRunetSearch(extendedRunetSearch: boolean): SourceType[] | null {
  return extendedRunetSearch ? null : [...MARKETPLACE_SOURCE_TYPES]
}

export type WordRange = {
  word: string
  start: number
  end: number
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
