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
