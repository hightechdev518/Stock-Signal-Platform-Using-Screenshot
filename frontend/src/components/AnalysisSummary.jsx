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

  // VWAP
  const vwapSignal = String(ind.vwap_signal || '')
  const vwap = ind.vwap ? `$${Number(ind.vwap).toFixed(2)}` : ''
  if (vwapSignal === 'bullish') {
    items.push({ type: 'ok', text: `Price above VWAP ${vwap} - institutional support` })
  } else if (vwapSignal === 'bearish') {
    items.push({ type: 'warn', text: `Price below VWAP ${vwap} - selling pressure` })
  }

  // ADX
  const adxSignal = String(ind.adx_signal || '')
  const trendStrength = String(ind.trend_strength || '')
  const adxVal = ind.adx ? Number(ind.adx).toFixed(1) : null
  if (adxVal) {
    if (adxSignal === 'bullish' && trendStrength === 'strong') {
      items.push({ type: 'ok', text: `ADX: ${adxVal} - Strong bullish trend confirmed` })
    } else if (adxSignal === 'bearish' && trendStrength === 'strong') {
      items.push({ type: 'warn', text: `ADX: ${adxVal} - Strong bearish trend confirmed` })
    } else {
      items.push({ type: 'warn', text: `ADX: ${adxVal} - Weak trend` })
    }
  }

  // CCI
  const cciSignal = String(ind.cci_signal || '')
  const cciVal = ind.cci ? Number(ind.cci).toFixed(1) : null
  if (cciVal) {
    if (cciSignal === 'oversold') {
      items.push({ type: 'ok', text: `CCI: ${cciVal} (oversold - potential reversal)` })
    } else if (cciSignal === 'overbought') {
      items.push({ type: 'warn', text: `CCI: ${cciVal} (overbought - potential pullback)` })
    }
  }

  // Support / Resistance
  const srSignal = String(ind.sr_signal || '')
  const support = ind.support ? `$${Number(ind.support).toFixed(2)}` : ''
  const resistance = ind.resistance ? `$${Number(ind.resistance).toFixed(2)}` : ''
  if (srSignal === 'near_support') {
    items.push({ type: 'ok', text: `Near key support ${support}` })
  } else if (srSignal === 'near_resistance') {
    items.push({ type: 'warn', text: `Near key resistance ${resistance}` })
  }

  // Pivot Points
  const pivotBias = String(ind.pivot_bias || '')
  const pivotSignal = String(ind.pivot_signal || '')
  const pivotR1 = ind.pivot_r1 ?
    `$${Number(ind.pivot_r1).toFixed(2)}` : ''
  const pivotS1 = ind.pivot_s1 ?
    `$${Number(ind.pivot_s1).toFixed(2)}` : ''

  if (pivotBias === 'strong_bullish') {
    items.push({ type: 'ok',
      text: 'Price above R2 pivot — very strong bullish' })
  } else if (pivotBias === 'bullish' &&
             pivotSignal === 'above_r1') {
    items.push({ type: 'ok',
      text: `Price above R1 pivot ${pivotR1} — bullish` })
  } else if (pivotBias === 'bullish') {
    items.push({ type: 'ok',
      text: 'Price above pivot point — bullish bias' })
  } else if (pivotBias === 'strong_bearish') {
    items.push({ type: 'warn',
      text: 'Price below S2 pivot — very strong bearish' })
  } else if (pivotBias === 'bearish' &&
             pivotSignal === 'below_s1') {
    items.push({ type: 'warn',
      text: `Price below S1 pivot ${pivotS1} — bearish` })
  } else if (pivotBias === 'bearish') {
    items.push({ type: 'warn',
      text: 'Price below pivot point — bearish bias' })
  }

  return items
}

export default function AnalysisSummary({ result }) {
  if (!result) return null
  const items = buildSummaryItems(result)
  const conclusion = result.conclusion

  return (
    <div className="bg-terminal-panel border border-terminal-border rounded p-2 flex flex-col overflow-hidden h-full">
      <h3 className="shrink-0 text-[13px] text-terminal-muted uppercase tracking-wide mb-1">
        Analysis Summary
      </h3>
      <ul className="flex-1 overflow-y-auto flex flex-col gap-1.5 min-h-0 mb-2">
        {items.map((item, i) => (
          <SummaryLine key={i} type={item.type} text={item.text} />
        ))}
      </ul>
      <div className="shrink-0 pt-2 border-t border-terminal-border">
        <h4 className="text-[12px] text-terminal-muted uppercase tracking-wide mb-1">Conclusion</h4>
        <p className="text-[12px] text-gray-400 leading-snug">{conclusion}</p>
      </div>
    </div>
  )
}
