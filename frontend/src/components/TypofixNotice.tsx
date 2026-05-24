import { getChangedWordIndexes, splitQueryParts } from '@/lib/utils'

type TypofixNoticeProps = {
  originalQuery: string
  correctedQuery: string
  onRevert: () => void
}

function QueryWithHighlights({
  query,
  changedWordIndexes
}: {
  query: string
  changedWordIndexes: Set<number>
}) {
  return (
    <>
      {splitQueryParts(query).map((part, index) => {
        if (part.type === 'space') {
          return <span key={`space-${index}`}>{part.value}</span>
        }

        return (
          <span
            className={
              changedWordIndexes.has(part.index)
                ? 'underline decoration-slate-600 decoration-wavy underline-offset-[4px]'
                : undefined
            }
            key={`word-${part.index}-${index}`}
          >
            {part.value}
          </span>
        )
      })}
    </>
  )
}

export function TypofixNotice({ originalQuery, correctedQuery, onRevert }: TypofixNoticeProps) {
  const changedWordIndexes = getChangedWordIndexes(originalQuery, correctedQuery)

  return (
    <p className="text-sm text-slate-600">
      Запрос исправлен на «
      <span className="font-medium text-slate-800">
        <QueryWithHighlights changedWordIndexes={changedWordIndexes} query={correctedQuery} />
      </span>
      ».{' '}
      <button
        className="cursor-pointer text-slate-900 underline decoration-slate-400 underline-offset-2 transition hover:text-slate-950"
        onClick={onRevert}
        type="button"
      >
        Вернуть «{originalQuery}»?
      </button>
    </p>
  )
}
