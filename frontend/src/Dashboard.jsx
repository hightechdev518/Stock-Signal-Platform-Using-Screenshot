import { useState } from 'react'
import { API_BASE } from './App'
import UploadZone from './components/UploadZone'
import SignalCard from './components/SignalCard'
import IndicatorGrid from './components/IndicatorGrid'
import ForecastPanel from './components/ForecastPanel'
import AnalysisSummary from './components/AnalysisSummary'

function PriceCard({ label, value, subtitle, accent }) {
  return (
    <div className="bg-terminal-panel border border-terminal-border rounded p-2 flex-1 min-w-0">
      <p className="text-[12px] text-terminal-muted uppercase truncate">{label}</p>
      <p className={`text-[20px] font-semibold truncate leading-tight ${accent || 'text-gray-100'}`}>
        {typeof value === 'number' ? `$${value}` : value}
      </p>
      <p className="text-[11px] text-gray-500 truncate">{subtitle}</p>
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

export default function Dashboard() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const analyze = async (file) => {
    setLoading(true)
    setError(null)
    setResult(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: formData })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Analysis failed')
      setResult(data)
    } catch (err) {
      setError(err.message || 'Could not analyze screenshot. Try a clearer image.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header className={`shrink-0 bg-terminal-panel/80 flex items-center justify-between ${
        result
          ? 'border-b border-terminal-border px-3 py-1.5'
          : 'border-b border-terminal-accent/60 px-8 py-4'
      }`}>
        <div>
          <h1 className={`${result ? 'text-[18px]' : 'text-[28px]'} font-bold text-terminal-accent leading-tight`}>
            STOCK SIGNAL ANALYZER
          </h1>
          <p className={`${result ? 'text-[12px]' : 'text-[14px]'} text-terminal-muted`}>
            Webull & TradingView • AI Analysis
          </p>
        </div>
        <div className={`flex items-center gap-2 ${result ? 'text-[12px]' : 'text-[14px]'}`}>
          <span className={`${result ? 'w-1.5 h-1.5' : 'w-2 h-2'} rounded-full bg-emerald-500 animate-pulse`} />
          <span className="text-gray-500">LIVE</span>
        </div>
      </header>

      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-3 py-2 gap-2">
        {!result && (
          <div className="flex-1 min-h-0 flex flex-col items-center justify-center gap-6 px-6">
            <UploadZone onUpload={analyze} loading={loading} />

            {loading && (
              <div className="flex items-center justify-center gap-2 shrink-0">
                <div className="w-5 h-5 border-2 border-terminal-accent border-t-transparent rounded-full animate-spin" />
                <p className="text-terminal-muted text-[13px]">Analyzing...</p>
              </div>
            )}

            {error && (
              <div className="shrink-0 w-full max-w-3xl bg-red-500/10 border border-red-500/50 rounded px-3 py-2 text-red-400 text-[13px] text-center">
                {error}
              </div>
            )}

            {!loading && !error && (
              <div className="grid grid-cols-3 gap-4 w-full max-w-5xl">
                <FeatureCard title="📸 Screenshot Analysis" text="Drop any Webull or TradingView chart screenshot" />
                <FeatureCard title="🤖 AI Signal" text="Get instant BUY/SELL/HOLD with 87%+ confidence" />
                <FeatureCard title="📊 Full Analysis" text="Entry price, TP, SL, and 4 forecast timeframes" />
              </div>
            )}
          </div>
        )}

        {result && <UploadZone onUpload={analyze} loading={loading} compact />}

        {result && !loading && (
          <div className="flex-1 flex flex-col min-h-0 gap-2 overflow-hidden">
            {/* Badges row */}
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

            {/* Main 2-column grid */}
            <div className="flex-1 grid grid-cols-2 gap-2 min-h-0 overflow-hidden">
              {/* Left column */}
              <div className="flex flex-col gap-2 min-h-0 overflow-hidden h-full">
                <div className="shrink-0">
                  <SignalCard signal={result.signal} confidence={result.confidence} compact />
                </div>
                <div className="shrink-0 flex flex-col gap-0">
                  <div className="flex gap-1.5">
                    <PriceCard
                      label="Buy At"
                      value={result.entry_price}
                      subtitle="Recommended entry price"
                    />
                    <PriceCard
                      label="Sell For Profit At"
                      value={result.take_profit}
                      subtitle="Target exit price"
                      accent="text-emerald-400"
                    />
                    <PriceCard
                      label="Sell To Cut Loss At"
                      value={result.stop_loss}
                      subtitle="Maximum loss price"
                      accent="text-red-400"
                    />
                  </div>
                  <div className="bg-terminal-panel border border-terminal-border rounded px-2 py-1.5 flex items-center justify-between">
                    <span className="text-[13px] text-terminal-muted">Risk / Reward</span>
                    <span className="text-[18px] font-bold text-terminal-accent">{result.risk_reward_ratio}</span>
                  </div>
                </div>
                <div className="flex-1 min-h-0">
                  <AnalysisSummary result={result} />
                </div>
              </div>

              {/* Right column - 2x2 forecasts */}
              <div className="grid grid-cols-2 grid-rows-2 gap-1.5 h-full min-h-0 overflow-hidden">
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

            {/* Indicators - single row */}
            <div className="shrink-0">
              <IndicatorGrid indicators={result.indicators} compact />
            </div>

            {/* Risk - single line */}
            {result.risk_assessment && (
              <div className="shrink-0 flex items-center gap-2 bg-amber-500/10 border border-amber-500/30 rounded px-2 py-1 text-[13px]">
                <span className="text-amber-400">⚠</span>
                <span className="text-amber-400/90 font-medium">Risk:</span>
                <span className="text-gray-400 truncate">{result.risk_assessment}</span>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
