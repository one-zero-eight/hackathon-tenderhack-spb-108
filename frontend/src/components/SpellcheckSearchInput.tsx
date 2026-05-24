import { apiFetch } from '@/api'
import {
  detectSpellcheckLanguage,
  getSpellcheckableWords,
  getWordAtCaret,
  splitQueryParts,
  type WordRange
} from '@/lib/utils'
import { Search, X } from 'lucide-react'
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject } from 'react'

const QUERY_SPELLCHECK_DEBOUNCE_MS = 500

type PopupAnchor = {
  left: number
  top: number
}

type SpellcheckSearchInputProps = {
  value: string
  onChange: (value: string) => void
  onCaretChange: (position: number) => void
  inputRef: RefObject<HTMLInputElement | null>
  disabled?: boolean
  id?: string
  placeholder?: string
}

function dismissedWordKey(start: number, word: string) {
  return `${start}:${word.toLowerCase()}`
}

export function SpellcheckSearchInput({
  value,
  onChange,
  onCaretChange,
  inputRef,
  disabled = false,
  id,
  placeholder
}: SpellcheckSearchInputProps) {
  const containerRef = useRef<HTMLSpanElement>(null)
  const mirrorRef = useRef<HTMLDivElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const querySpellcheckRequestId = useRef(0)
  const popoverRequestId = useRef(0)

  const [isFocused, setIsFocused] = useState(false)
  const [spellcheckSuggestions, setSpellcheckSuggestions] = useState<string[]>([])
  const [popoverTarget, setPopoverTarget] = useState<WordRange | null>(null)
  const [misspelledWords, setMisspelledWords] = useState<Set<string>>(new Set())
  const [dismissedWords, setDismissedWords] = useState<Set<string>>(new Set())
  const [popupAnchor, setPopupAnchor] = useState<PopupAnchor | null>(null)

  const dismissedWordsRef = useRef(dismissedWords)
  dismissedWordsRef.current = dismissedWords
  const dismissedWordsKey = useMemo(
    () => [...dismissedWords].sort().join('\0'),
    [dismissedWords]
  )

  const popoverTargetKey = popoverTarget
    ? dismissedWordKey(popoverTarget.start, popoverTarget.word)
    : null
  const showSpellcheckSuggestions =
    isFocused &&
    popoverTarget !== null &&
    popoverTargetKey !== null &&
    spellcheckSuggestions.length > 0 &&
    !dismissedWords.has(popoverTargetKey)

  const syncCaretPosition = (input: HTMLInputElement) => {
    onCaretChange(input.selectionStart ?? input.value.length)
  }

  const closePopover = () => {
    popoverRequestId.current += 1
    setPopoverTarget(null)
    setSpellcheckSuggestions([])
    setPopupAnchor(null)
  }

  const measurePopupAnchor = (wordStart: number) => {
    if (!mirrorRef.current || !containerRef.current) return

    const span = mirrorRef.current.querySelector<HTMLElement>(`[data-word-start="${wordStart}"]`)
    if (!span) return

    const spanRect = span.getBoundingClientRect()
    const containerRect = containerRef.current.getBoundingClientRect()
    const nextAnchor = {
      left: spanRect.left - containerRect.left + spanRect.width / 2,
      top: spanRect.top - containerRect.top
    }
    setPopupAnchor((current) =>
      current &&
      current.left === nextAnchor.left &&
      current.top === nextAnchor.top
        ? current
        : nextAnchor
    )
  }

  useLayoutEffect(() => {
    if (!showSpellcheckSuggestions || popoverTarget === null) {
      setPopupAnchor((current) => (current === null ? current : null))
      return
    }

    measurePopupAnchor(popoverTarget.start)
  }, [showSpellcheckSuggestions, popoverTarget?.start, value])

  useEffect(() => {
    if (!showSpellcheckSuggestions || popoverTarget === null) return

    const handleReposition = () => measurePopupAnchor(popoverTarget.start)
    window.addEventListener('resize', handleReposition)
    return () => window.removeEventListener('resize', handleReposition)
  }, [showSpellcheckSuggestions, popoverTarget?.start, value])

  useEffect(() => {
    const requestId = querySpellcheckRequestId.current + 1
    querySpellcheckRequestId.current = requestId

    const words = getSpellcheckableWords(value)
    if (words.length === 0) {
      setMisspelledWords((current) => (current.size === 0 ? current : new Set()))
      return
    }

    const timeoutId = window.setTimeout(async () => {
      const nextMisspelled = new Set<string>()
      const dismissed = dismissedWordsRef.current

      await Promise.all(
        words.map(async ({ word, start }) => {
          if (dismissed.has(dismissedWordKey(start, word))) return

          const language = detectSpellcheckLanguage(word)
          if (!language) return

          const { data, error } = await apiFetch.POST('/search/spellcheck', {
            body: { word, language }
          })

          if (requestId !== querySpellcheckRequestId.current) return
          if (error || !data?.suggestions?.length) return

          nextMisspelled.add(word.toLowerCase())
        })
      )

      if (requestId === querySpellcheckRequestId.current) {
        setMisspelledWords((current) => {
          if (
            current.size === nextMisspelled.size &&
            [...current].every((word) => nextMisspelled.has(word))
          ) {
            return current
          }
          return nextMisspelled
        })
      }
    }, QUERY_SPELLCHECK_DEBOUNCE_MS)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [value, dismissedWordsKey])

  const openPopoverForWord = async (wordRange: WordRange) => {
    const key = dismissedWordKey(wordRange.start, wordRange.word)
    if (dismissedWordsRef.current.has(key)) return

    const language = detectSpellcheckLanguage(wordRange.word)
    if (!language) return

    const requestId = popoverRequestId.current + 1
    popoverRequestId.current = requestId

    setPopoverTarget(wordRange)
    setSpellcheckSuggestions([])
    setPopupAnchor(null)

    const { data, error } = await apiFetch.POST('/search/spellcheck', {
      body: {
        word: wordRange.word,
        language
      }
    })

    if (requestId !== popoverRequestId.current) return

    if (error || !data?.suggestions?.length) {
      setPopoverTarget(null)
      return
    }

    setSpellcheckSuggestions(data.suggestions)
  }

  const handleInputClick = (input: HTMLInputElement) => {
    syncCaretPosition(input)
    const wordRange = getWordAtCaret(value, input.selectionStart ?? input.value.length)
    if (!wordRange || wordRange.word.length <= 2) {
      closePopover()
      return
    }

    if (!isWordMisspelled(wordRange.start, wordRange.word)) {
      closePopover()
      return
    }

    void openPopoverForWord(wordRange)
  }

  const handleApplySpellcheckSuggestion = (suggestion: string) => {
    if (!popoverTarget) return

    const nextValue = `${value.slice(0, popoverTarget.start)}${suggestion}${value.slice(
      popoverTarget.end
    )}`
    const nextCaretPosition = popoverTarget.start + suggestion.length

    closePopover()
    onChange(nextValue)
    onCaretChange(nextCaretPosition)

    window.requestAnimationFrame(() => {
      const input = inputRef.current
      if (!input) return

      input.focus()
      input.setSelectionRange(nextCaretPosition, nextCaretPosition)
    })
  }

  const handleDismissSuggestions = (ignoreWord = false) => {
    if (!popoverTarget) return

    if (ignoreWord) {
      setDismissedWords((current) => {
        const next = new Set(current)
        next.add(dismissedWordKey(popoverTarget.start, popoverTarget.word))
        return next
      })
    }

    closePopover()
  }

  const isWordMisspelled = (start: number, word: string) =>
    !dismissedWords.has(dismissedWordKey(start, word)) && misspelledWords.has(word.toLowerCase())

  return (
    <span className="relative" ref={containerRef}>
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 z-20 size-5 -translate-y-1/2 text-slate-400"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-10 overflow-visible rounded-md pl-10 pr-3"
        ref={mirrorRef}
      >
        <div className="flex h-11 items-center whitespace-pre text-sm text-slate-950">
          {splitQueryParts(value).map((part, index) => {
            if (part.type === 'space') {
              return <span key={`space-${index}`}>{part.value}</span>
            }

            return (
              <span
                className={
                  isWordMisspelled(part.start, part.value)
                    ? 'underline decoration-red-500 decoration-wavy underline-offset-[6px]'
                    : undefined
                }
                data-word-start={part.start}
                key={`word-${part.index}-${index}`}
              >
                {part.value}
              </span>
            )
          })}
        </div>
      </div>
      <input
        className="relative z-0 h-11 w-full rounded-md border border-slate-300 bg-transparent pl-10 pr-3 text-sm text-transparent caret-slate-950 outline-none transition placeholder:text-slate-400 selection:bg-slate-200/80 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={disabled}
        onBlur={(event) => {
          const nextTarget = event.relatedTarget
          if (nextTarget && containerRef.current?.contains(nextTarget)) return
          setIsFocused(false)
          closePopover()
        }}
        onChange={(event) => {
          closePopover()
          onChange(event.target.value)
          syncCaretPosition(event.target)
        }}
        onClick={(event) => handleInputClick(event.currentTarget)}
        onFocus={(event) => {
          setIsFocused(true)
          syncCaretPosition(event.currentTarget)
        }}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.preventDefault()
            if (showSpellcheckSuggestions) {
              handleDismissSuggestions(false)
            }
            return
          }

          if (event.key.length === 1 || event.key === 'Backspace' || event.key === 'Delete') {
            closePopover()
          }
        }}
        onKeyUp={(event) => syncCaretPosition(event.currentTarget)}
        onSelect={(event) => syncCaretPosition(event.currentTarget)}
        placeholder={placeholder}
        id={id}
        ref={inputRef}
        required
        spellCheck={false}
        type="text"
        value={value}
      />
      {showSpellcheckSuggestions && popupAnchor && popoverTarget ? (
        <div
          className="absolute z-30 flex max-w-[calc(100%-1rem)] items-center gap-1 rounded-lg border border-slate-200 bg-white py-1 pl-2 pr-1 shadow-[0_8px_24px_-8px_rgba(15,23,42,0.35)]"
          ref={popoverRef}
          style={{
            left: popupAnchor.left,
            top: popupAnchor.top,
            transform: 'translate(-50%, calc(-100% - 6px))'
          }}
        >
          <div className="flex min-w-0 items-center gap-0.5">
            {spellcheckSuggestions.map((suggestion, index) => (
              <span className="flex items-center" key={suggestion}>
                {index > 0 ? <span className="px-0.5 text-slate-300">·</span> : null}
                <button
                  className="cursor-pointer rounded px-1.5 py-0.5 text-sm font-medium text-slate-900 transition hover:bg-slate-100"
                  onClick={() => handleApplySpellcheckSuggestion(suggestion)}
                  onMouseDown={(event) => event.preventDefault()}
                  type="button"
                >
                  {suggestion}
                </button>
              </span>
            ))}
          </div>
          <button
            aria-label="Закрыть подсказки"
            className="flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            onClick={() => handleDismissSuggestions(true)}
            onMouseDown={(event) => event.preventDefault()}
            type="button"
          >
            <X className="size-3.5" />
          </button>
        </div>
      ) : null}
    </span>
  )
}
