import { useEffect, useMemo, useRef, useState } from 'react'
import { API_BASE } from '../App'

const CATEGORIES = [
  { id: 'gainers', label: '🚀 Top Gainers' },
  { id: 'losers', label: '📉 Top Losers' },
  { id: 'active', label: '🔥 Most Active' },
  { id: 'all', label: '📊 All Stocks' },
]

function formatPrice(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return Number(value).toFixed(2)
}

function formatSigned(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const num = Number(value)
  const prefix = num > 0 ? '+' : ''
  return `${prefix}${num.toFixed(2)}`
}

function formatCompact(value) {
  if (value == null || value === 0) return '—'
  const num = Number(value)
  if (Number.isNaN(num)) return '—'
  const abs = Math.abs(num)
  if (abs >= 1e9) return `${(num / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${(num / 1e6).toFixed(1)}M`
  if (abs >= 1e3) return `${(num / 1e3).toFixed(1)}K`
  return String(num)
}

function truncateName(name, max = 12) {
  if (!name) return '—'
  return name.length > max ? `${name.slice(0, max)}…` : name
}

const formatPct = (val) => {
  if (val == null) return { text: '—', color: '#556677' }
  if (val > 0) return {
    text: `+${val.toFixed(2)}%`,
    color: '#00cc66',
  }
  if (val < 0) return {
    text: `${val.toFixed(2)}%`,
    color: '#ff4444',
  }
  return { text: '0.00%', color: '#556677' }
}

const PERIOD_PCT_FIELDS = [
  { header: '3D %', key: 'change_3d' },
  { header: '1W %', key: 'change_1w' },
  { header: '15D %', key: 'change_15d' },
  { header: '1M %', key: 'change_1m' },
  { header: '3M %', key: 'change_3m' },
]

function SignalBadge({ signal }) {
  const colors = {
    BUY: 'text-emerald-400 border-emerald-400/30 bg-emerald-400/10',
    SELL: 'text-red-400 border-red-400/30 bg-red-400/10',
    HOLD: 'text-amber-400 border-amber-400/30 bg-amber-400/10',
  }
  const value = signal || 'HOLD'
  return (
    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap ${colors[value] || colors.HOLD}`}>
      {value}
    </span>
  )
}

function Sparkline({ data }) {
  const width = 80
  const height = 32
  const pad = 2

  if (!data || data.length < 2) {
    return <svg width={width} height={height} className="block shrink-0" />
  }

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const points = data
    .map((value, index) => {
      const x = pad + (index / (data.length - 1)) * (width - pad * 2)
      const y = pad + (1 - (value - min) / range) * (height - pad * 2)
      return `${x},${y}`
    })
    .join(' ')

  const stroke = data[data.length - 1] > data[0] ? '#34d399' : '#f87171'

  return (
    <svg width={width} height={height} className="block shrink-0">
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={points}
      />
    </svg>
  )
}

function StockTable({ stocks, onSelect, selectedTickers = new Set(), onToggle }) {
  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <table className="w-full min-w-max border-collapse text-[12px]">
        <thead className="sticky top-0 z-10 bg-terminal-panel border-b border-terminal-border">
          <tr className="text-terminal-muted text-left">
            <th className="px-2 py-1.5 w-6"></th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap">Symbol</th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap">Name</th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap">Signal</th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap">Sparkline</th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap text-right">Price</th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap text-right">Change</th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap text-right">% Change</th>
            {PERIOD_PCT_FIELDS.map(({ header }) => (
              <th key={header} className="px-2 py-1.5 font-medium whitespace-nowrap text-right">
                {header}
              </th>
            ))}
            <th className="px-2 py-1.5 font-medium whitespace-nowrap text-right">Prev Close</th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap text-right">Open</th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap text-right">High</th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap text-right">Low</th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap text-right">Volume</th>
            <th className="px-2 py-1.5 font-medium whitespace-nowrap text-right">Market Cap</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock, index) => {
            const changePositive = (stock.change ?? 0) >= 0
            const pctPositive = (stock.change_pct ?? 0) >= 0
            const changeColor = changePositive ? 'text-emerald-400' : 'text-red-400'
            const pctColor = pctPositive ? 'text-emerald-400' : 'text-red-400'

            return (
              <tr
                key={stock.ticker}
                onClick={() => onSelect(stock.ticker)}
                className={`cursor-pointer border-b border-terminal-border/50 hover:bg-terminal-accent/10 ${
                  index % 2 === 0 ? 'bg-terminal-panel/30' : 'bg-terminal-panel/10'
                }`}
              >
                <td className="px-2 py-1.5" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selectedTickers.has(stock.ticker)}
                    onChange={() => onToggle(stock.ticker)}
                    className="accent-yellow-400 cursor-pointer"
                  />
                </td>
                <td className="px-2 py-1.5 font-bold text-terminal-accent whitespace-nowrap">
                  {stock.ticker}
                </td>
                <td className="px-2 py-1.5 text-gray-300 whitespace-nowrap" title={stock.name}>
                  {truncateName(stock.name)}
                </td>
                <td className="px-2 py-1.5">
                  <SignalBadge signal={stock.signal} />
                </td>
                <td className="px-2 py-1.5">
                  <Sparkline data={stock.sparkline} />
                </td>
                <td className="px-2 py-1.5 text-right text-gray-100 whitespace-nowrap">
                  {formatPrice(stock.price)}
                </td>
                <td className={`px-2 py-1.5 text-right whitespace-nowrap ${changeColor}`}>
                  {formatSigned(stock.change)}
                </td>
                <td className={`px-2 py-1.5 text-right whitespace-nowrap ${pctColor}`}>
                  {formatSigned(stock.change_pct)}%
                </td>
                {PERIOD_PCT_FIELDS.map(({ key }) => {
                  const { text, color } = formatPct(stock[key])
                  return (
                    <td
                      key={key}
                      className="px-2 py-1.5 text-right whitespace-nowrap text-[12px]"
                      style={{ color }}
                    >
                      {text}
                    </td>
                  )
                })}
                <td className="px-2 py-1.5 text-right text-gray-500 whitespace-nowrap">
                  {formatPrice(stock.prev_close)}
                </td>
                <td className="px-2 py-1.5 text-right text-gray-500 whitespace-nowrap">
                  {formatPrice(stock.open)}
                </td>
                <td className="px-2 py-1.5 text-right text-emerald-400 whitespace-nowrap">
                  {formatPrice(stock.high)}
                </td>
                <td className="px-2 py-1.5 text-right text-red-400 whitespace-nowrap">
                  {formatPrice(stock.low)}
                </td>
                <td className="px-2 py-1.5 text-right text-gray-300 whitespace-nowrap">
                  {formatCompact(stock.volume)}
                </td>
                <td className="px-2 py-1.5 text-right text-gray-300 whitespace-nowrap">
                  {formatCompact(stock.market_cap)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

const scannerCache = {}

const DEFAULT_FILTERS = {
  minCap: 0,
  maxCap: '',
  minRoe: 0,
  maxRoe: '',
  maConditions: {
    bullish: false,
    bearish: false,
    strongBullish: false,
    strongBearish: false,
  },
}

function noMaxLimit(max) {
  return max === '' || max == null || Number(max) === 0
}

function getMaTrendText(stock) {
  return String(stock.ma_trend_label || stock.ma_trend || '').toLowerCase()
}

function passesMarketCap(stock, filters) {
  const cap = stock.market_cap ? Number(stock.market_cap) : null
  if (cap === null) return true
  const minVal = (Number(filters.minCap) || 0) * 1_000_000_000
  if (cap < minVal) return false
  if (!noMaxLimit(filters.maxCap)) {
    const maxVal = Number(filters.maxCap) * 1_000_000_000
    if (cap > maxVal) return false
  }
  return true
}

function passesRoe(stock, filters) {
  // ROE filter - only apply to stocks with valid ROE data
  if (stock.roe != null && stock.roe > 0) {
    const maxRoe = filters.maxRoe > 0 ? filters.maxRoe : Infinity
    if (stock.roe < filters.minRoe || stock.roe > maxRoe) return false
  }
  return true
}

function passesMa(stock, filters) {
  const { maConditions } = filters
  const any = Object.values(maConditions).some(Boolean)
  if (!any) return true

  const t = getMaTrendText(stock)
  const checks = []

  if (maConditions.bullish) {
    checks.push(
      (t.includes('above all') && t.includes('bullish') && !t.includes('strong')) ||
      t === 'bullish'
    )
  }
  if (maConditions.bearish) {
    checks.push(
      (t.includes('below all') && t.includes('bearish') && !t.includes('strong')) ||
      (t === 'bearish' && !t.includes('strong'))
    )
  }
  if (maConditions.strongBullish) {
    checks.push(t.includes('strong bullish'))
  }
  if (maConditions.strongBearish) {
    checks.push(t.includes('strong bearish'))
  }

  return checks.some(Boolean)
}

function filterStocks(stocks, filters) {
  return stocks.filter(
    (stock) =>
      passesMarketCap(stock, filters) &&
      passesRoe(stock, filters) &&
      passesMa(stock, filters)
  )
}

function FilterPanel({ stocks, filters, onChange, onReset }) {
  const [maDropdownOpen, setMaDropdownOpen] = useState(false)
  const maDropdownRef = useRef(null)

  const inputClass =
    'w-16 px-1.5 py-0.5 bg-[#0d0d0d] border border-terminal-border rounded text-[11px] text-gray-200 focus:border-terminal-accent outline-none'

  const capMatches = stocks.filter((s) => passesMarketCap(s, filters)).length
  const roeMatches = stocks.filter((s) => passesRoe(s, filters)).length
  const maMatches = stocks.filter((s) => passesMa(s, filters)).length

  const selectedMaConditions = Object.values(filters.maConditions).filter(Boolean)

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (maDropdownRef.current &&
          !maDropdownRef.current.contains(e.target)) {
        setMaDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener(
      'mousedown', handleClickOutside
    )
  }, [])

  const rowClass =
    'flex items-center gap-3 px-3 py-2.5 text-[11px] border-b border-terminal-border/60 last:border-b-0'

  return (
    <div className="shrink-0 bg-[#141414] border border-terminal-border rounded overflow-visible">
      <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-terminal-border/60">
        <span className="text-[11px] font-semibold text-terminal-accent uppercase tracking-wide">
          Filters
        </span>
        <button
          type="button"
          onClick={onReset}
          className="text-[11px] px-2 py-0.5 border border-terminal-border rounded text-terminal-muted hover:text-terminal-accent hover:border-terminal-accent transition-colors"
        >
          Reset
        </button>
      </div>

      <div className={rowClass}>
        <span className="text-terminal-muted shrink-0 w-20">Market Cap</span>
        <div className="flex items-center gap-1.5 flex-1">
          <input
            type="number"
            step="0.01"
            value={filters.minCap}
            onChange={(e) => onChange({ ...filters, minCap: Number(e.target.value) })}
            className={inputClass}
          />
          <span className="text-gray-500">B</span>
          <span className="text-gray-600">to</span>
          <input
            type="number"
            step="0.01"
            value={filters.maxCap}
            placeholder="No limit"
            onChange={(e) => onChange({ ...filters, maxCap: e.target.value })}
            className={inputClass}
          />
          <span className="text-gray-500">B</span>
        </div>
        <span className="text-terminal-accent shrink-0 whitespace-nowrap">
          Matches: {capMatches}
        </span>
      </div>

      <div className={rowClass}>
        <span className="text-terminal-muted shrink-0 w-20">ROE</span>
        <div className="flex items-center gap-1.5 flex-1">
          <input
            type="number"
            step="0.1"
            value={filters.minRoe}
            onChange={(e) => onChange({ ...filters, minRoe: Number(e.target.value) })}
            className={inputClass}
          />
          <span className="text-gray-500">%</span>
          <span className="text-gray-600">to</span>
          <input
            type="number"
            step="0.1"
            value={filters.maxRoe}
            placeholder="No limit"
            onChange={(e) => onChange({ ...filters, maxRoe: e.target.value })}
            className={inputClass}
          />
          <span className="text-gray-500">%</span>
        </div>
        <span className="text-terminal-accent shrink-0 whitespace-nowrap">
          Matches: {roeMatches}
        </span>
      </div>

      <div className={rowClass}>
        <span className="text-terminal-muted shrink-0 w-20">MA</span>
        <div ref={maDropdownRef} style={{ position: 'relative' }} className="flex-1">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              console.log('MA button clicked, current state:', maDropdownOpen)
              setMaDropdownOpen((prev) => !prev)
              console.log('MA dropdown should now be:', !maDropdownOpen)
            }}
            className="w-full text-left px-2 py-0.5 bg-[#0d0d0d] border border-terminal-border rounded text-gray-200 hover:border-terminal-accent transition-colors"
          >
            {selectedMaConditions.length} condition(s) &gt;
          </button>
          {maDropdownOpen && (
            <div
              style={{
                position: 'absolute',
                zIndex: 9999,
                background: '#1a1f2e',
                border: '1px solid #2a3040',
                borderRadius: '4px',
                padding: '8px',
                minWidth: '200px',
                top: '100%',
                left: 0,
                marginTop: '4px',
              }}
            >
              {[
                { key: 'bullish', label: 'Bullish' },
                { key: 'bearish', label: 'Bearish' },
                { key: 'strongBullish', label: 'Strong Bullish' },
                { key: 'strongBearish', label: 'Strong Bearish' },
              ].map(({ key, label }) => (
                <label
                  key={key}
                  className="flex items-center gap-2 text-[11px] text-gray-300 cursor-pointer hover:text-gray-100 py-0.5"
                >
                  <input
                    type="checkbox"
                    checked={filters.maConditions[key]}
                    onChange={(e) =>
                      onChange({
                        ...filters,
                        maConditions: {
                          ...filters.maConditions,
                          [key]: e.target.checked,
                        },
                      })
                    }
                    className="accent-terminal-accent"
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          )}
        </div>
        <span className="text-terminal-accent shrink-0 whitespace-nowrap">
          Matches: {maMatches}
        </span>
      </div>
    </div>
  )
}

export default function StockScanner({ onSelectTicker }) {
  const [category, setCategory] = useState('gainers')
  const [stocks, setStocks] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const fetchingRef = useRef(false)
  const [folders, setFolders] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('scanner_folders') || '{}')
    } catch {
      return {}
    }
  })
  const [activeFolder, setActiveFolder] = useState(null)
  const [selectedTickers, setSelectedTickers] = useState(new Set())
  const [showFolderMenu, setShowFolderMenu] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')

  const saveFolders = (updated) => {
    setFolders(updated)
    localStorage.setItem('scanner_folders', JSON.stringify(updated))
  }

  const createFolder = (name) => {
    if (!name.trim()) return
    const updated = { ...folders, [name.trim()]: [] }
    saveFolders(updated)
    setNewFolderName('')
  }

  const addToFolder = (folderName) => {
    if (!folders[folderName]) return
    const existing = new Set(folders[folderName])
    selectedTickers.forEach((t) => existing.add(t))
    const updated = {
      ...folders,
      [folderName]: [...existing],
    }
    saveFolders(updated)
    setSelectedTickers(new Set())
    setShowFolderMenu(false)
  }

  const deleteFolder = (name) => {
    const updated = { ...folders }
    delete updated[name]
    saveFolders(updated)
    if (activeFolder === name) setActiveFolder(null)
  }

  const toggleTicker = (ticker) => {
    setSelectedTickers((prev) => {
      const next = new Set(prev)
      if (next.has(ticker)) next.delete(ticker)
      else next.add(ticker)
      return next
    })
  }

  const filteredStocks = useMemo(() => {
    let base = stocks
    if (activeFolder && folders[activeFolder]) {
      base = stocks.filter((s) => folders[activeFolder].includes(s.ticker))
    }
    return filterStocks(base, filters)
  }, [stocks, filters, activeFolder, folders])

  const fetchScanner = async (cat, forceRefresh = false) => {
    const cache = scannerCache[cat]
    const tenMinutes = 10 * 60 * 1000
    if (!forceRefresh && cache &&
        (Date.now() - cache.timestamp) < tenMinutes) {
      setStocks(cache.stocks)
      setLastUpdated(cache.time)
      return
    }
    if (fetchingRef.current) return
    fetchingRef.current = true
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `${API_BASE}/scanner?category=${cat}`
      )
      if (!res.ok) throw new Error('Scanner failed')
      const data = await res.json()
      const time = new Date().toLocaleTimeString()
      scannerCache[cat] = {
        stocks: data.stocks || [],
        time,
        timestamp: Date.now()
      }
      setStocks(data.stocks || [])
      setLastUpdated(time)
    } catch (e) {
      setError('Failed to load scanner data')
    } finally {
      setLoading(false)
      fetchingRef.current = false
    }
  }

  const fetchAll = async (forceRefresh = false) => {
    const tenMinutes = 10 * 60 * 1000
    const allFresh = ['gainers','losers','active','all'].every(cat => {
      const cache = scannerCache[cat]
      return cache && (Date.now() - cache.timestamp) < tenMinutes
    })
    if (!forceRefresh && allFresh) {
      setStocks(scannerCache[category].stocks)
      setLastUpdated(scannerCache[category].time)
      return
    }
    if (fetchingRef.current) return
    fetchingRef.current = true
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/scanner/all`)
      if (!res.ok) throw new Error('Scanner failed')
      const data = await res.json()
      const time = new Date().toLocaleTimeString()
      const timestamp = Date.now()
      ;['gainers','losers','active','all'].forEach(cat => {
        scannerCache[cat] = {
          stocks: data[cat] || [],
          time,
          timestamp
        }
      })
      setStocks(scannerCache[category].stocks || [])
      setLastUpdated(time)
    } catch(e) {
      setError('Failed to load scanner data')
    } finally {
      setLoading(false)
      fetchingRef.current = false
    }
  }

  useEffect(() => {
    if (scannerCache[category]) {
      setStocks(scannerCache[category].stocks)
      setLastUpdated(scannerCache[category].time)
    }
  }, [category])

  useEffect(() => {
    fetchAll()
  }, [])

  return (
    <div className="flex flex-col h-full min-h-0 gap-2">
      <div className="shrink-0 flex items-center justify-between">
        <h2 className="text-[14px] font-bold text-terminal-accent uppercase tracking-wide">
          Stock Scanner
        </h2>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-[11px] text-gray-500">Updated {lastUpdated}</span>
          )}
          <button
            type="button"
            onClick={() => setFiltersOpen((open) => !open)}
            className={`text-[11px] px-2 py-1 border rounded transition-colors ${
              filtersOpen
                ? 'border-terminal-accent text-terminal-accent bg-terminal-accent/10'
                : 'border-terminal-border text-terminal-muted hover:text-terminal-accent hover:border-terminal-accent'
            }`}
          >
            Filters
          </button>
          <button
            type="button"
            onClick={() => {
              ['gainers','losers','active','all']
                .forEach(cat => delete scannerCache[cat])
              fetchAll(true)
            }}
            disabled={loading}
            className="text-[11px] px-2 py-1 border border-terminal-border rounded text-terminal-muted hover:text-terminal-accent hover:border-terminal-accent transition-colors"
          >
            {loading ? 'Loading...' : '↻ Refresh'}
          </button>
        </div>
      </div>

      <div className="shrink-0 flex gap-1.5 flex-wrap">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            type="button"
            onClick={() => {
              setCategory(cat.id)
              setActiveFolder(null)
            }}
            className={`text-[11px] px-2 py-1 rounded border transition-colors ${
              category === cat.id
                ? 'border-terminal-accent text-terminal-accent bg-terminal-accent/10'
                : 'border-terminal-border text-terminal-muted hover:border-terminal-accent'
            }`}
          >
            {cat.label}
          </button>
        ))}
        {Object.keys(folders).map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => {
              setActiveFolder(name)
              setCategory('all')
            }}
            className={`text-[11px] px-2 py-1 rounded border transition-colors flex items-center gap-1 ${
              activeFolder === name
                ? 'border-yellow-400 text-yellow-400 bg-yellow-400/10'
                : 'border-terminal-border text-terminal-muted hover:border-yellow-400'
            }`}
          >
            📁 {name}
            <span
              onClick={(e) => {
                e.stopPropagation()
                deleteFolder(name)
              }}
              className="ml-1 text-gray-600 hover:text-red-400 cursor-pointer"
            >
              ×
            </span>
          </button>
        ))}
      </div>

      <div className="shrink-0 flex items-center gap-2 flex-wrap">
        {selectedTickers.size > 0 && (
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowFolderMenu((p) => !p)}
              className="text-[11px] px-2 py-1 border border-yellow-400/50 rounded text-yellow-400 hover:border-yellow-400 transition-colors"
            >
              Save {selectedTickers.size} to folder ▾
            </button>
            {showFolderMenu && (
              <div className="absolute top-full left-0 mt-1 bg-[#141414] border border-terminal-border rounded z-50 min-w-[160px]">
                {Object.keys(folders).map((name) => (
                  <button
                    key={name}
                    type="button"
                    onClick={() => addToFolder(name)}
                    className="w-full text-left px-3 py-1.5 text-[11px] text-gray-300 hover:bg-terminal-accent/10 hover:text-terminal-accent"
                  >
                    📁 {name}
                  </button>
                ))}
                {Object.keys(folders).length === 0 && (
                  <p className="px-3 py-2 text-[11px] text-gray-600">No folders yet</p>
                )}
              </div>
            )}
          </div>
        )}
        <div className="flex items-center gap-1">
          <input
            type="text"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && createFolder(newFolderName)}
            placeholder="New folder name..."
            className="text-[11px] px-2 py-0.5 bg-[#0d0d0d] border border-terminal-border rounded text-gray-200 focus:border-yellow-400 outline-none w-32"
          />
          <button
            type="button"
            onClick={() => createFolder(newFolderName)}
            className="text-[11px] px-2 py-0.5 border border-terminal-border rounded text-terminal-muted hover:text-yellow-400 hover:border-yellow-400 transition-colors"
          >
            + Folder
          </button>
        </div>
        {activeFolder && (
          <button
            type="button"
            onClick={() => setActiveFolder(null)}
            className="text-[11px] px-2 py-0.5 border border-terminal-border rounded text-gray-500 hover:text-gray-300 transition-colors"
          >
            ✕ Clear folder filter
          </button>
        )}
      </div>

      {filtersOpen && (
        <FilterPanel
          stocks={stocks}
          filters={filters}
          onChange={setFilters}
          onReset={() => setFilters(DEFAULT_FILTERS)}
        />
      )}

      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        {loading && (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <div className="w-48 h-1.5 bg-terminal-border rounded-full overflow-hidden">
              <div className="h-full bg-terminal-accent rounded-full animate-pulse w-full" />
            </div>
            <p className="text-terminal-muted text-[13px]">
              Scanning {stocks.length > 0 ? stocks.length : ''} stocks...
            </p>
            <p className="text-gray-600 text-[11px]">
              Analyzing with ML model — takes ~30 seconds
            </p>
          </div>
        )}
        {error && (
          <div className="flex items-center justify-center h-full">
            <p className="text-red-400 text-[13px]">{error}</p>
          </div>
        )}
        {!loading && !error && stocks.length > 0 && (
          <>
            <p className="shrink-0 text-[11px] text-terminal-muted px-1">
              Showing {filteredStocks.length} of {stocks.length} stocks
            </p>
            <StockTable
              stocks={filteredStocks}
              onSelect={onSelectTicker}
              selectedTickers={selectedTickers}
              onToggle={toggleTicker}
            />
          </>
        )}
        {!loading && !error && stocks.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-terminal-muted text-[13px]">No stocks found</p>
          </div>
        )}
      </div>
    </div>
  )
}
