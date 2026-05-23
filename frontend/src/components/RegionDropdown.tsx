import { regions, type RegionName } from '@/lib/regions'
import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

export function RegionDropdown({
  selectedRegion,
  onSelect
}: {
  selectedRegion: RegionName
  onSelect: (region: RegionName) => void
}) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="relative flex flex-col gap-2">
      <span className="text-sm font-medium text-slate-700">Выбор региона</span>
      <button
        aria-expanded={isOpen}
        className="flex h-11 w-full items-center justify-between gap-3 rounded-md border border-slate-300 bg-white px-3 text-left text-sm outline-none transition focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
        onClick={() => setIsOpen((current) => !current)}
        type="button"
      >
        <span className="truncate">{selectedRegion}</span>
        <ChevronDown
          aria-hidden="true"
          className={`size-4 shrink-0 text-slate-500 transition ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen ? (
        <div className="absolute left-0 right-0 top-full z-20 mt-2 max-h-72 overflow-y-auto rounded-md border border-slate-200 bg-white py-1 shadow-lg">
          {regions.map((region, index) => (
            <button
              className={`block w-full px-3 py-2 text-left text-sm transition hover:bg-slate-100 ${
                region === selectedRegion ? 'font-medium text-slate-950' : 'text-slate-700'
              } ${index === 0 ? 'sticky top-0 z-10 border-b border-slate-200 bg-white' : ''}`}
              key={region}
              onClick={() => {
                onSelect(region)
                setIsOpen(false)
              }}
              type="button"
            >
              {region}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
