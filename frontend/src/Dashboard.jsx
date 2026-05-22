import { useCallback, useEffect, useRef, useState } from 'react'
import { API_BASE } from './App'
import UploadZone from './components/UploadZone'
import SignalCard from './components/SignalCard'
import IndicatorGrid from './components/IndicatorGrid'
import ForecastPanel from './components/ForecastPanel'
import AnalysisSummary from './components/AnalysisSummary'
import LiveModeBar from './components/LiveModeBar'

function PriceCard({ label, value, subtitle, detail, accent }) {
  return (
    <div className="bg-terminal-panel border border-terminal-border rounded p-2 flex-1 min-w-0">
      <p className="text-[12px] text-terminal-muted uppercase truncate">{label}</p>
      <p className={`text-[20px] font-semibold truncate leading-tight ${accent || 'text-gray-100'}`}>
        {typeof value === 'number' ? `$${value}` : value}
      </p>
      <p className="text-[11px] text-gray-500 truncate">{subtitle}</p>
      {detail && <p className="text-[11px] text-terminal-accent truncate">{detail}</p>}
    </div>
  )
}

function FeatureCard({ title, text }) {
  return (
    <div className="bg-terminal-panel/80 border border-terminal-border rounded-xl px-5 py-4 text-center">
      <h3 className="text-[17px] font-semibold text-gray-100 mb-2">{title}</h3>
      <p className="text-[13px] text-terminal-muted leading-snug">{text}</p>
    </div>
  )
}

function ResultsView({ result, signalPulse, compactUpload, onUpload, loading }) {
  const buyTime = result?.buy_at?.time === 'Now - Current price'
    ? 'Entry now - Current price'
    : result?.buy_at?.time || 'Entry now - Current price'
  const sellProfitTime = result?.short_term_forecast?.predicted_by ||
    result?.sell_for_profit?.predicted_time ||
    result?.short_term_forecast?.timeframe

  return (
    <div className="flex-1 flex flex-col min-h-0 gap-2 overflow-hidden">
      {compactUpload && <UploadZone onUpload={onUpload} loading={loading} compact />}

      <div className="shrink-0 flex flex-wrap gap-1.5 text-[13px]">
        <span className="px-2 py-0.5 bg-terminal-panel border border-terminal-border rounded">
          Platform: <strong className="text-terminal-accent">{result.platform}</strong>
        </span>
        <span className="px-2 py-0.5 bg-terminal-panel border border-terminal-border rounded">
          Ticker: <strong>{result.ticker}</strong>
        </span>
        <span className="px-2 py-0.5 bg-terminal-panel border border-terminal-border rounded">
          TF: <strong>{result.timeframe}</strong>
        </span>
        <span className="px-2 py-0.5 bg-terminal-panel border border-terminal-border rounded text-gray-500">
          {new Date(result.timestamp).toLocaleString()}
        </span>
      </div>

      <div className="flex-1 grid grid-cols-2 gap-2 min-h-0 overflow-hidden">
        <div className="flex flex-col gap-2 min-h-0 overflow-hidden h-full">
          <div className="shrink-0">
            <SignalCard
              signal={result.signal}
              confidence={result.confidence}
              compact
              pulse={signalPulse}
            />
          </div>
          <div className="shrink-0 flex flex-col gap-0">
            <div className="flex gap-1.5">
              <PriceCard
                label="Buy At"
                value={result.buy_at?.price ?? result.entry_price}
                subtitle="Recommended entry price"
                detail={buyTime}
              />
              <PriceCard
                label="Sell For Profit At"
                value={result.sell_for_profit?.price ?? result.take_profit}
                subtitle="Target exit price"
                detail={sellProfitTime}
                accent="text-emerald-400"
              />
              <PriceCard
                label="Sell To Cut Loss At"
                value={result.sell_to_cut_loss?.price ?? result.stop_loss}
                subtitle={result.sell_to_cut_loss?.note || 'Maximum loss price'}
                accent="text-red-400"
              />
            </div>
            <div className="bg-terminal-panel border border-terminal-border rounded px-2 py-1.5 flex items-center justify-between">
              <span className="text-[13px] text-terminal-muted">Risk / Reward</span>
              <span className="text-[18px] font-bold text-terminal-accent">{result.risk_reward_ratio}</span>
            </div>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            <AnalysisSummary result={result} />
          </div>
        </div>

        <div className="grid grid-cols-2 grid-rows-3 gap-1.5 h-full min-h-0 overflow-hidden">
          <div className="min-h-0 h-full">
            <ForecastPanel title="SAME DAY" forecast={result.same_day_forecast} compact panelId="same_day" result={result} />
          </div>
          <div className="min-h-0 h-full">
            <ForecastPanel title="SAME WEEK" forecast={result.same_week_forecast} compact panelId="same_week" result={result} />
          </div>
          <div className="min-h-0 h-full">
            <ForecastPanel title="Short-Term" forecast={result.short_term_forecast} compact panelId="short" result={result} />
          </div>
          <div className="min-h-0 h-full">
            <ForecastPanel title="Medium-Term" forecast={result.medium_term_forecast} compact panelId="medium" result={result} />
          </div>
          <div className="min-h-0 h-full">
            <ForecastPanel title="Long-Term" forecast={result.long_term_forecast} compact panelId="long" result={result} />
          </div>
          <div className="min-h-0 h-full">
            <ForecastPanel title="Monthly" forecast={result.monthly_forecast} compact panelId="monthly" result={result} />
          </div>
        </div>
      </div>

      <div className="shrink-0">
        <IndicatorGrid indicators={result.indicators} compact />
      </div>

      {result.risk_assessment && (
        <div className="shrink-0 flex items-center gap-2 bg-amber-500/10 border border-amber-500/30 rounded px-2 py-1 text-[13px]">
          <span className="text-amber-400">⚠</span>
          <span className="text-amber-400/90 font-medium">Risk:</span>
          <span className="text-gray-400 truncate">{result.risk_assessment}</span>
        </div>
      )}
    </div>
  )
}

export default function Dashboard() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [liveMode, setLiveMode] = useState(false)
  const [ticker, setTicker] = useState('')
  const [liveActive, setLiveActive] = useState(false)
  const [lastUpdated, setLastUpdated] = useState('')
  const [secondsAgo, setSecondsAgo] = useState(0)
  const [priceFlash, setPriceFlash] = useState(null)
  const [signalPulse, setSignalPulse] = useState(false)
  const [backendOnline, setBackendOnline] = useState(false)
  const [backendReconnecting, setBackendReconnecting] = useState(true)

  const prevPriceRef = useRef(null)

  useEffect(() => {
    let cancelled = false

    const checkBackend = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(5000) })
        if (cancelled) return
        setBackendOnline(res.ok)
        setBackendReconnecting(!res.ok)
      } catch {
        if (cancelled) return
        setBackendOnline(false)
        setBackendReconnecting(true)
      }
    }

    checkBackend()
    const interval = setInterval(checkBackend, 3000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  const analyze = async (file) => {
    setLoading(true)
    setError(null)
    setResult(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: formData })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || data.error || 'Analysis failed')
      setResult(data)
    } catch (err) {
      setError(err.message || 'Could not analyze screenshot. Try a clearer image.')
    } finally {
      setLoading(false)
    }
  }

  const fetchLiveData = useCallback(async () => {
    const symbol = ticker.trim().toUpperCase()
    if (!symbol) return

    try {
      const res = await fetch(`${API_BASE}/live/${symbol}`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Live fetch failed')

      const price = data.price ?? data.entry_price
      if (prevPriceRef.current != null && price != null) {
        if (price > prevPriceRef.current) setPriceFlash('up')
        else if (price < prevPriceRef.current) setPriceFlash('down')
        setTimeout(() => setPriceFlash(null), 800)
      }
      prevPriceRef.current = price

      setResult(data)
      setLastUpdated(new Date().toLocaleTimeString())
      setSecondsAgo(0)
      setSignalPulse(true)
      setTimeout(() => setSignalPulse(false), 600)
      setError(null)
    } catch (err) {
      setError(err.message || 'Could not fetch live data.')
    }
  }, [ticker])

  useEffect(() => {
    if (!liveMode || !liveActive || !ticker.trim()) return undefined

    fetchLiveData()
    const interval = setInterval(fetchLiveData, 5000)
    return () => clearInterval(interval)
  }, [liveMode, liveActive, ticker, fetchLiveData])

  useEffect(() => {
    if (!liveActive) return undefined
    const timer = setInterval(() => setSecondsAgo((s) => s + 1), 1000)
    return () => clearInterval(timer)
  }, [liveActive, lastUpdated])

  const handleToggleLiveMode = () => {
    setLiveMode((on) => {
      if (on) {
        setLiveActive(false)
        setResult(null)
        prevPriceRef.current = null
      }
      return !on
    })
    setError(null)
  }

  const handleStartLive = () => {
    if (!ticker.trim()) return
    setLiveActive(true)
    setResult(null)
    prevPriceRef.current = null
    setError(null)
  }

  const handleStopLive = () => {
    setLiveActive(false)
    prevPriceRef.current = null
  }

  const showResults = Boolean(result) && (!loading || liveActive)
  const showUpload = !liveMode

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header className={`shrink-0 bg-terminal-panel/80 flex items-center justify-between ${
        showResults
          ? 'border-b border-terminal-border px-3 py-1.5'
          : 'border-b border-terminal-accent/60 px-8 py-4'
      }`}>
        <div>
          <h1 className={`${showResults ? 'text-[18px]' : 'text-[28px]'} font-bold text-terminal-accent leading-tight`}>
            STOCK SIGNAL ANALYZER
          </h1>
          <p className={`${showResults ? 'text-[12px]' : 'text-[14px]'} text-terminal-muted`}>
            {liveMode ? 'Live Day Trading • Real-Time Signals' : 'Webull & TradingView • AI Analysis'}
          </p>
        </div>
        <div className={`flex items-center gap-2 ${showResults ? 'text-[12px]' : 'text-[14px]'}`}>
          {backendOnline ? (
            <>
              <span className={`${showResults ? 'w-1.5 h-1.5' : 'w-2 h-2'} rounded-full bg-emerald-500 ${liveActive ? 'animate-pulse' : ''}`} />
              <span className="text-emerald-400 font-semibold">LIVE</span>
            </>
          ) : backendReconnecting ? (
            <>
              <span className={`${showResults ? 'w-1.5 h-1.5' : 'w-2 h-2'} rounded-full bg-amber-500 animate-pulse`} />
              <span className="text-amber-400 font-semibold">Reconnecting...</span>
            </>
          ) : (
            <>
              <span className={`${showResults ? 'w-1.5 h-1.5' : 'w-2 h-2'} rounded-full bg-gray-600`} />
              <span className="text-gray-500">OFFLINE</span>
            </>
          )}
        </div>
      </header>

      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-3 py-2 gap-2">
        <LiveModeBar
          liveMode={liveMode}
          onToggleLiveMode={handleToggleLiveMode}
          ticker={ticker}
          onTickerChange={setTicker}
          liveActive={liveActive}
          onStart={handleStartLive}
          onStop={handleStopLive}
          result={result}
          priceFlash={priceFlash}
          secondsAgo={secondsAgo}
          lastUpdated={lastUpdated}
        />

        {error && (
          <div className="shrink-0 bg-red-500/10 border border-red-500/50 rounded px-3 py-2 text-red-400 text-[13px] text-center">
            {error}
          </div>
        )}

        {!showResults && showUpload && (
          <div className="flex-1 min-h-0 flex flex-col items-center justify-center gap-6 px-6">
            <UploadZone onUpload={analyze} loading={loading} />

            {loading && (
              <div className="flex items-center justify-center gap-2 shrink-0">
                <div className="w-5 h-5 border-2 border-terminal-accent border-t-transparent rounded-full animate-spin" />
                <p className="text-terminal-muted text-[13px]">Analyzing...</p>
              </div>
            )}

            {!loading && !error && (
              <div className="grid grid-cols-3 gap-4 w-full max-w-5xl">
                <FeatureCard title="📸 Screenshot Analysis" text="Drop any Webull or TradingView chart screenshot" />
                <FeatureCard title="📡 Live Mode" text="Real-time price and signals every 5 seconds for day trading" />
                <FeatureCard title="📊 Full Analysis" text="Entry price, TP, SL, and 4 forecast timeframes" />
              </div>
            )}
          </div>
        )}

        {!showResults && liveMode && !liveActive && (
          <div className="flex-1 flex items-center justify-center text-terminal-muted text-[14px]">
            Enter a ticker and click Start Live Analysis
          </div>
        )}

        {showResults && (
          <ResultsView
            result={result}
            signalPulse={signalPulse}
            compactUpload={showUpload && !liveActive}
            onUpload={analyze}
            loading={loading}
          />
        )}
      </main>
    </div>
  )
}
