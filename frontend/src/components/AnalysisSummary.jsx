function SummaryLine({ type, text }) {
  const icon = type === 'ok' ? '✅' : type === 'warn' ? '⚠️' : '•'
  const color = type === 'ok' ? 'text-emerald-400/90' : type === 'warn' ? 'text-amber-400/90' : 'text-gray-400'
  return (
    <li className={`flex items-center gap-1.5 text-[13px] leading-snug ${color}`}>
      <span className="shrink-0 text-[12px]">{icon}</span>
      <span className="min-w-0">{text}</span>
    </li>
  )
}

function buildSummaryItems(result) {
  const ind = result.indicators || {}
  const items = []

  const maTrend = String(ind.MA_trend || '')
  if (maTrend.toLowerCase().includes('bullish') || maTrend.toLowerCase().includes('above')) {
    items.push({ type: 'ok', text: maTrend })
  } else if (maTrend.toLowerCase().includes('bearish') || maTrend.toLowerCase().includes('below')) {
    items.push({ type: 'warn', text: maTrend })
  } else if (maTrend) {
    items.push({ type: 'warn', text: maTrend })
  }

  const vol = String(ind.volume || '')
  if (/very high|high|3x|2x/i.test(vol)) {
    items.push({ type: 'ok', text: `High volume breakout (${vol})` })
  } else if (/low/i.test(vol)) {
    items.push({ type: 'warn', text: `Volume: ${vol}` })
  } else if (vol) {
    items.push({ type: 'warn', text: `Volume: ${vol}` })
  }

  const rsi = ind.RSI
  if (rsi != null) {
    if (rsi > 70) {
      items.push({ type: 'warn', text: `RSI: ${rsi} (overbought)` })
    } else if (rsi < 30) {
      items.push({ type: 'ok', text: `RSI: ${rsi} (oversold - potential bounce)` })
    } else {
      items.push({ type: 'ok', text: `RSI: ${rsi} (neutral - not overbought)` })
    }
  }

  const macd = ind.MACD
  if (macd != null && macd !== '') {
    const macdText = String(macd)
    if (/bull/i.test(macdText)) {
      items.push({ type: 'ok', text: `MACD: ${macdText}` })
    } else if (/bear/i.test(macdText)) {
      items.push({ type: 'warn', text: `MACD: ${macdText}` })
    } else {
      items.push({ type: 'warn', text: `MACD: ${macdText}` })
    }
  }

  const mom = String(ind.momentum || '')
  if (/strong/i.test(mom)) {
    items.push({ type: 'ok', text: `Momentum: ${mom}` })
  } else if (mom) {
    items.push({ type: 'warn', text: `Momentum: ${mom}` })
  }

  const bb = String(ind.bollinger || '')
  if (/upper|breakout/i.test(bb)) {
    items.push({ type: 'ok', text: `Bollinger: ${bb}` })
  } else if (/lower/i.test(bb)) {
    items.push({ type: 'warn', text: `Bollinger: ${bb}` })
  } else if (bb) {
    items.push({ type: 'warn', text: `Bollinger: ${bb}` })
  }

  if (result.risk_assessment) {
    const risk = result.risk_assessment
    const isHigh = /high|medium-high/i.test(risk)
    items.push({ type: isHigh ? 'warn' : 'ok', text: risk })
  }

  return items
}

function buildConclusion(items, result) {
  const bullish = items.filter((i) => i.type === 'ok').length
  const warnings = items.filter((i) => i.type === 'warn').length
  const signal = result.signal || 'HOLD'
  const bias = signal === 'BUY' ? 'BULLISH' : signal === 'SELL' ? 'BEARISH' : 'NEUTRAL'
  const action =
    signal === 'BUY'
      ? 'Consider entering at current price with strict risk management.'
      : signal === 'SELL'
        ? 'Consider reducing exposure or waiting for confirmation.'
        : 'Wait for a clearer setup before taking action.'

  return `Based on ${bullish} bullish signals and ${warnings} warnings, the overall bias is ${bias}. ${action}`
}

export default function AnalysisSummary({ result }) {
  if (!result) return null
  const items = buildSummaryItems(result)
  const conclusion = buildConclusion(items, result)

  return (
    <div className="flex-1 bg-terminal-panel border border-terminal-border rounded p-2 flex flex-col justify-between h-full overflow-hidden">
      <div className="flex-1 flex flex-col min-h-0">
        <h3 className="text-[13px] text-terminal-muted uppercase tracking-wide mb-2">
          Analysis Summary
        </h3>
        <ul className="flex flex-col gap-2 min-h-0">
          {items.map((item, i) => (
            <SummaryLine key={i} type={item.type} text={item.text} />
          ))}
        </ul>
      </div>

      <div className="pt-2 mt-auto border-t border-terminal-border">
        <h4 className="text-[12px] text-terminal-muted uppercase tracking-wide mb-1">Conclusion</h4>
        <p className="text-[12px] text-gray-400 leading-snug">{conclusion}</p>
      </div>
    </div>
  )
}
