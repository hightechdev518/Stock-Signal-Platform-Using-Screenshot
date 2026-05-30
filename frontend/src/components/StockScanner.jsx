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

function StockTable({ stocks, onSelect, selectedTickers = new Set(), onToggle, sortConfig = { key: null, direction: 'asc' }, onSort }) {
  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <table className="w-full min-w-max border-collapse text-[12px]">
        <thead>
          <tr className="text-left text-[11px] text-terminal-muted border-b border-terminal-border sticky top-0 bg-[#0a0a0a] z-10">
            <th className="px-2 py-1.5 w-6"></th>
            {[
              { label: 'Symbol', key: 'ticker' },
              { label: 'Name', key: 'name' },
              { label: 'Signal', key: 'signal' },
              { label: 'Sparkline', key: null },
              { label: 'Price', key: 'price' },
              { label: 'Change', key: 'change' },
              { label: '% Change', key: 'change_pct' },
              { label: '3D %', key: 'change_3d' },
              { label: '1W %', key: 'change_1w' },
              { label: '15D %', key: 'change_15d' },
              { label: '1M %', key: 'change_1m' },
              { label: '3M %', key: 'change_3m' },
              { label: 'Prev Close', key: 'prev_close' },
              { label: 'Open', key: 'open' },
              { label: 'High', key: 'high' },
              { label: 'Low', key: 'low' },
              { label: 'Volume', key: 'volume' },
              { label: 'Market Cap', key: 'market_cap' },
            ].map(({ label, key }) => (
              <th
                key={label}
                className={`px-2 py-1.5 whitespace-nowrap ${key ? 'cursor-pointer hover:text-terminal-accent select-none' : ''}`}
                onClick={() => key && onSort(key)}
              >
                {label}
                {key && sortConfig.key === key && (
                  <span className="ml-1">
                    {sortConfig.direction === 'asc' ? '▲' : '▼'}
                  </span>
                )}
              </th>
            ))}
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

const DEFAULT_TABLE_FILTERS = {
  marketCapMin: 0,
  marketCapMax: 999,
  roeMin: -9999,
  roeMax: 9999,
  maFilter: 'off',
}

const passesTableMarketCap = (stock, marketCapMin, marketCapMax) => {
  if (stock.market_cap == null ||
      stock.market_cap === undefined ||
      stock.market_cap === "" ||
      stock.market_cap === 0) return true
  const mc = Number(stock.market_cap)
  if (isNaN(mc)) return true
  const minRaw = Number(marketCapMin) * 1_000_000_000
  const maxRaw = Number(marketCapMax) * 1_000_000_000
  return mc >= minRaw && mc <= maxRaw
}

const passesTableRoe = (stock, roeMin, roeMax) => {
  if (stock.roe == null) return true
  const roe = Number(stock.roe)
  return roe >= Number(roeMin) && roe <= Number(roeMax)
}

function passesTableMaFilter(stock, maFilter) {
  if (maFilter === 'off') return true
  const price = Number(stock.price)
  if (Number.isNaN(price)) return true

  const maKey = { ma5: 'ma5', ma10: 'ma10', ma20: 'ma20' }[maFilter]
  if (!maKey) return true

  const maVal = stock[maKey]
  if (maVal == null) return true
  const ma = Number(maVal)
  if (Number.isNaN(ma)) return true
  return price > ma
}

function applyTableFilters(stocks, { marketCapMin, marketCapMax, roeMin, roeMax, maFilter }) {
  const isDefaultFilters =
    (marketCapMin === 0 || marketCapMin === '0') &&
    (marketCapMax === 999 || marketCapMax === '999') &&
    (roeMin === -9999 || roeMin === '-9999') &&
    (roeMax === 9999 || roeMax === '9999') &&
    (maFilter === 'off' || maFilter === 'Off')

  if (isDefaultFilters) {
    return stocks
  }

  return stocks.filter(
    (stock) =>
      passesTableMarketCap(stock, marketCapMin, marketCapMax) &&
      passesTableRoe(stock, roeMin, roeMax) &&
      passesTableMaFilter(stock, maFilter)
  )
}

export default function StockScanner({ onSelectTicker }) {
  const [category, setCategory] = useState('gainers')
  const [stocks, setStocks] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
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

  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' })

  const [marketCapMin, setMarketCapMin] = useState(DEFAULT_TABLE_FILTERS.marketCapMin)
  const [marketCapMax, setMarketCapMax] = useState(DEFAULT_TABLE_FILTERS.marketCapMax)
  const [roeMin, setRoeMin] = useState(DEFAULT_TABLE_FILTERS.roeMin)
  const [roeMax, setRoeMax] = useState(DEFAULT_TABLE_FILTERS.roeMax)
  const [maFilter, setMaFilter] = useState(DEFAULT_TABLE_FILTERS.maFilter)

  const [scanComplete, setScanComplete] = useState(false)
  const [totalCached, setTotalCached] = useState(0)
  const prevCountRef = useRef(0)
  const stableCountRef = useRef(0)
  const autoRefreshRef = useRef(null)

  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }))
  }

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

  const resetTableFilters = () => {
    setMarketCapMin(DEFAULT_TABLE_FILTERS.marketCapMin)
    setMarketCapMax(DEFAULT_TABLE_FILTERS.marketCapMax)
    setRoeMin(DEFAULT_TABLE_FILTERS.roeMin)
    setRoeMax(DEFAULT_TABLE_FILTERS.roeMax)
    setMaFilter(DEFAULT_TABLE_FILTERS.maFilter)
  }

  const filteredStocks = useMemo(() => {
    let base = stocks
    if (activeFolder && folders[activeFolder]) {
      base = stocks.filter(s => 
        folders[activeFolder].includes(s.ticker)
      )
    }
    let sorted = ['gainers', 'losers', 'active'].includes(category)
      ? base
      : applyTableFilters(base, { marketCapMin, marketCapMax, roeMin, roeMax, maFilter })
    if (sortConfig.key) {
      sorted = [...sorted].sort((a, b) => {
        const aVal = a[sortConfig.key] ?? -Infinity
        const bVal = b[sortConfig.key] ?? -Infinity
        if (typeof aVal === 'string') {
          return sortConfig.direction === 'asc'
            ? aVal.localeCompare(bVal)
            : bVal.localeCompare(aVal)
        }
        return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal
      })
    }
    return sorted
  }, [stocks, activeFolder, folders, sortConfig, category, marketCapMin, marketCapMax, roeMin, roeMax, maFilter])

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

  useEffect(() => {
    const startTime = Date.now()

    autoRefreshRef.current = setInterval(async () => {
      if (Date.now() - startTime > 3600000) {
        clearInterval(autoRefreshRef.current)
        return
      }
      await fetchScanner('all', true)
      try {
        const statusRes = await fetch(
          'http://127.0.0.1:8000/scanner/status'
        )
        const status = await statusRes.json()
        if (!status.scanning) {
          setScanComplete(true)
          clearInterval(autoRefreshRef.current)
        }
      } catch(e) {}
      setTotalCached(prev => {
        const current = stocks.length
        if (current === prevCountRef.current) {
          stableCountRef.current += 1
          if (stableCountRef.current >= 5 && stocks.length >= 100) {
            setScanComplete(true)
            clearInterval(autoRefreshRef.current)
          }
        } else {
          stableCountRef.current = 0
          setScanComplete(false)
        }
        prevCountRef.current = current
        return current
      })
    }, 20000)

    return () => clearInterval(autoRefreshRef.current)
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
            <div className="shrink-0 flex flex-wrap items-center gap-x-4 gap-y-2 px-2 py-1.5 bg-[#141414] border border-terminal-border rounded text-[11px]">
              <div className="flex items-center gap-1.5">
                <span className="text-terminal-muted whitespace-nowrap">Market Cap</span>
                <label className="flex items-center gap-1 text-gray-400">
                  <span>Min $B</span>
                  <input
                    type="number"
                    step="0.1"
                    value={marketCapMin}
                    onChange={(e) => setMarketCapMin(Number(e.target.value))}
                    className="w-14 px-1.5 py-0.5 bg-[#0d0d0d] border border-terminal-border rounded text-gray-200 focus:border-terminal-accent outline-none"
                  />
                </label>
                <label className="flex items-center gap-1 text-gray-400">
                  <span>Max $B</span>
                  <input
                    type="number"
                    step="0.1"
                    value={marketCapMax}
                    placeholder="No limit"
                    onChange={(e) => setMarketCapMax(Number(e.target.value))}
                    className="w-14 px-1.5 py-0.5 bg-[#0d0d0d] border border-terminal-border rounded text-gray-200 focus:border-terminal-accent outline-none"
                  />
                </label>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-terminal-muted whitespace-nowrap">ROE</span>
                <label className="flex items-center gap-1 text-gray-400">
                  <span>Min %</span>
                  <input
                    type="number"
                    step="0.1"
                    value={roeMin}
                    placeholder="No limit"
                    onChange={(e) => setRoeMin(Number(e.target.value))}
                    className="w-14 px-1.5 py-0.5 bg-[#0d0d0d] border border-terminal-border rounded text-gray-200 focus:border-terminal-accent outline-none"
                  />
                </label>
                <label className="flex items-center gap-1 text-gray-400">
                  <span>Max %</span>
                  <input
                    type="number"
                    step="0.1"
                    value={roeMax}
                    placeholder="No limit"
                    onChange={(e) => setRoeMax(Number(e.target.value))}
                    className="w-14 px-1.5 py-0.5 bg-[#0d0d0d] border border-terminal-border rounded text-gray-200 focus:border-terminal-accent outline-none"
                  />
                </label>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-terminal-muted whitespace-nowrap">MA Filter</span>
                <select
                  value={maFilter}
                  onChange={(e) => setMaFilter(e.target.value)}
                  className="px-1.5 py-0.5 bg-[#0d0d0d] border border-terminal-border rounded text-gray-200 focus:border-terminal-accent outline-none"
                >
                  <option value="off">Off</option>
                  <option value="ma5">Above MA5</option>
                  <option value="ma10">Above MA10</option>
                  <option value="ma20">Above MA20</option>
                </select>
              </div>
              <button
                type="button"
                onClick={resetTableFilters}
                className="text-[11px] px-2 py-0.5 border border-terminal-border rounded text-terminal-muted hover:text-terminal-accent hover:border-terminal-accent transition-colors"
              >
                Reset
              </button>
            </div>
            <div className="shrink-0 text-[11px] text-terminal-muted px-1">
              <div style={{ marginBottom: '6px' }}>
                {stocks.length > 0 && !scanComplete ? (
                  <span style={{ color: '#00ccff' }}>
                    ⟳ Scanning... {stocks.length} stocks loaded
                  </span>
                ) : stocks.length > 0 && scanComplete ? (
                  <span style={{ color: '#00ff88', fontWeight: 'bold' }}>
                    ✓ Scan complete — {stocks.length} stocks
                  </span>
                ) : null}
              </div>
              <div>
                Showing {filteredStocks.length} of {stocks.length} stocks
              </div>
            </div>
            <StockTable
              stocks={filteredStocks}
              onSelect={onSelectTicker}
              selectedTickers={selectedTickers}
              onToggle={toggleTicker}
              sortConfig={sortConfig}
              onSort={handleSort}
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
