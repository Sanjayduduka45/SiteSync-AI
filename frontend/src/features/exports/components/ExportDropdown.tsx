/**
 * ExportDropdown — Reusable export action dropdown component.
 * Allows downloading complete project datasets in CSV or JSON formats.
 */

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { downloadExport, formatExportError } from '../api'
import type { ExportDataset, ExportFormat } from '../types'

interface ExportDropdownProps {
  projectId: string
  dataset: ExportDataset
  datasetLabel?: string
  variant?: 'default' | 'outline'
  size?: 'default' | 'sm'
}

export function ExportDropdown({
  projectId,
  dataset,
  datasetLabel,
  variant = 'outline',
  size = 'sm',
}: ExportDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleExport = async (format: ExportFormat) => {
    setIsOpen(false)
    setIsExporting(true)
    setErrorMessage(null)
    try {
      await downloadExport(projectId, dataset, format)
    } catch (err) {
      setErrorMessage(formatExportError(err))
    } finally {
      setIsExporting(false)
    }
  }

  const label = datasetLabel || 'Export'

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <Button
        variant={variant}
        size={size}
        disabled={isExporting || !projectId}
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-1.5 font-medium text-xs shadow-2xs text-gray-700 bg-white hover:bg-gray-50 border-gray-300"
        aria-expanded={isOpen}
        aria-haspopup="true"
        aria-label={`Export ${label}`}
      >
        {isExporting ? (
          <>
            <span className="w-3.5 h-3.5 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" aria-hidden="true" />
            <span>Exporting...</span>
          </>
        ) : (
          <>
            <svg
              className="w-3.5 h-3.5 text-gray-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            <span>{label}</span>
            <svg
              className="w-3 h-3 text-gray-400 ml-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </>
        )}
      </Button>

      {isOpen && (
        <div
          className="origin-top-right absolute right-0 mt-1.5 w-44 rounded-lg shadow-lg bg-white ring-1 ring-black/5 border border-gray-100 z-50 py-1 focus:outline-none"
          role="menu"
          aria-orientation="vertical"
        >
          <button
            type="button"
            onClick={() => handleExport('csv')}
            className="w-full text-left px-3.5 py-2 text-xs text-gray-700 hover:bg-amber-50/70 hover:text-amber-900 flex items-center justify-between transition-colors"
            role="menuitem"
          >
            <span>Export CSV</span>
            <span className="text-[10px] uppercase font-mono text-gray-400 font-semibold bg-gray-50 px-1 py-0.5 rounded border">
              .csv
            </span>
          </button>
          <button
            type="button"
            onClick={() => handleExport('json')}
            className="w-full text-left px-3.5 py-2 text-xs text-gray-700 hover:bg-amber-50/70 hover:text-amber-900 flex items-center justify-between transition-colors"
            role="menuitem"
          >
            <span>Export JSON</span>
            <span className="text-[10px] uppercase font-mono text-gray-400 font-semibold bg-gray-50 px-1 py-0.5 rounded border">
              .json
            </span>
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="absolute right-0 top-full mt-2 w-64 p-2 bg-rose-50 border border-rose-200 rounded-md text-[11px] text-rose-700 shadow-md z-50" role="alert">
          <div className="flex items-start justify-between gap-1">
            <span>{errorMessage}</span>
            <button
              type="button"
              onClick={() => setErrorMessage(null)}
              className="text-rose-500 hover:text-rose-800 font-bold"
              aria-label="Dismiss export error"
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
