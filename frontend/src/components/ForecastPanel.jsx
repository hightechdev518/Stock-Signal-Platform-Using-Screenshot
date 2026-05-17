function getPanelMidLines(panelId, result) {
  if (!result) return []
  const ind = result.indicators || {}
  const risk = result.risk_assessment || 'Moderate'
  const volShort = /high|medium-high/i.test(risk) ? 'Medium-High' : 'Moderate'
  const signal = result.signal || 'HOLD'
  const maTrend = String(ind.MA_trend || '')
  const maAlign = /bullish|above/i.test(maTrend) ? 'All bullish' : /bearish|below/i.test(maTrend) ? 'All bearish' : 'Mixed'
  const trendStrength = `Trend strength: ${ind.momentum || 'Moderate'} ${signal === 'BUY' ? 'bullish' : signal === 'SELL' ? 'bearish' : ''}`.trim()

  switch (panelId) {
    case 'short':
      return [
        `Volatility: ${volShort}`,
        `Confidence: ${result.confidence ?? '—'}%`,
      ]
    case 'medium':
      return [
        `Trend: ${result.medium_term_forecast?.direction || 'Uptrend'} continuation`,
        `Volume: ${ind.volume || 'Normal volume'}`,
      ]
    case 'long': {
      const rsi = ind.RSI
      const macd = ind.MACD
      if (rsi != null && macd != null) {
        const rsiLabel = rsi > 70 ? 'Overbought' : rsi < 30 ? 'Oversold' : 'Neutral zone'
        return [
          `RSI: ${rsi} - ${rsiLabel}`,
          `MACD: ${/bull/i.test(String(macd)) ? 'Bullish crossover confirmed' : macd}`,
        ]
      }
      return [trendStrength, `MA alignment: ${maAlign}`]
    }
    case 'monthly': {
      return [
        `MA Alignment: ${maAlign}`,
        `Momentum: ${ind.momentum || 'Moderate'}`,
      ]
    }
    default:
      return []
  }
}

function getPanelExtras(panelId, result) {
  if (!result) return []
  const ind = result.indicators || {}
  const signal = result.signal || 'HOLD'
  const strength = signal === 'BUY' || signal === 'SELL' ? 'Strong' : 'Moderate'
  const maTrend = String(ind.MA_trend || '')
  const maAlign = /bullish|above/i.test(maTrend) ? 'All bullish' : /bearish|below/i.test(maTrend) ? 'All bearish' : 'Mixed'
  const risk = result.risk_assessment || 'Moderate'

  switch (panelId) {
    case 'short':
      return [
        `Entry signal strength: ${strength}`,
        'Suggested position size: 2-3% of portfolio',
      ]
    case 'medium':
      return [
        `Key resistance: $${result.take_profit}`,
        `Key support: $${result.stop_loss}`,
      ]
    case 'long':
      return [
        `Breakout status: ${/bullish|above/i.test(maTrend) ? 'Confirmed above MA20' : 'Watching MA20 support'}`,
        `Momentum: ${ind.momentum || 'Moderate'}`,
      ]
    case 'monthly':
      return [
        signal === 'BUY' ? 'Accumulation phase detected' : signal === 'SELL' ? 'Distribution phase detected' : 'Consolidation phase',
        `Risk level: ${risk.replace(' detected', '').replace(' volatility', '')}`,
      ]
    default:
      return []
  }
}

function Row({ label, value, valueClass = 'text-gray-100' }) {
  return (
    <div className="flex justify-between gap-1">
      <span className="text-[12px] text-gray-500 shrink-0">{label}</span>
      <span className={`text-[13px] truncate text-right ${valueClass}`}>{value}</span>
    </div>
  )
}

function DetailLine({ text }) {
  return <p className="text-gray-400 text-[12px] leading-snug">{text}</p>
}

function panelTimeframe(panelId, fallback) {
  switch (panelId) {
    case 'short':
      return 'Timeframe: 2-4 hours'
    case 'medium':
      return 'Timeframe: 3-7 days'
    case 'long':
      return 'Timeframe: 2-4 weeks'
    case 'monthly':
      return 'Timeframe: 1-3 months'
    default:
      return `Timeframe: ${fallback}`
  }
}

export default function ForecastPanel({ title, forecast, compact = false, panelId, result }) {
  if (!forecast) return null

  const dirColor =
    forecast.direction?.toLowerCase().includes('bull') ||
    forecast.direction?.toLowerCase().includes('up')
      ? 'text-emerald-400'
      : forecast.direction?.toLowerCase().includes('bear') ||
          forecast.direction?.toLowerCase().includes('down')
        ? 'text-red-400'
        : 'text-amber-400'

  const midLines = compact && panelId ? getPanelMidLines(panelId, result) : []
  const extras = compact && panelId ? getPanelExtras(panelId, result) : []

  if (compact) {
    const detailLines = [panelTimeframe(panelId, forecast.timeframe), ...midLines, ...extras]

    return (
      <div className="bg-terminal-panel border border-terminal-border rounded p-2 h-full flex flex-col gap-2">
        <h3 className="text-[13px] text-terminal-muted uppercase tracking-wide">{title}</h3>
        <div className="space-y-1">
          <Row label="Direction" value={forecast.direction} valueClass={`font-semibold ${dirColor}`} />
          <Row label="Target" value={`$${forecast.target}`} />
          <Row label="Timeframe" value={forecast.timeframe} valueClass="text-gray-400" />
          <p className="text-gray-500 text-[12px] leading-snug">{forecast.note}</p>
        </div>

        <div className="flex-1 rounded bg-black/10 border border-terminal-border/50 p-2 flex flex-col justify-evenly gap-1">
          {detailLines.map((line, i) => (
            <DetailLine key={`detail-${i}`} text={line} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-terminal-panel border border-terminal-border rounded-lg p-4">
      <h3 className="text-terminal-muted text-[13px] uppercase tracking-wider mb-3">{title}</h3>
      <div className="space-y-2">
        <Row label="Direction" value={forecast.direction} valueClass={`font-semibold ${dirColor}`} />
        <Row label="Target" value={`$${forecast.target}`} />
        <Row label="Timeframe" value={forecast.timeframe} valueClass="text-gray-300" />
        <p className="text-gray-400 text-sm pt-2 border-t border-terminal-border">{forecast.note}</p>
      </div>
    </div>
  )
}
