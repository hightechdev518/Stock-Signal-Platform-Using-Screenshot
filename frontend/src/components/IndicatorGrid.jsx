export default function IndicatorGrid({ indicators, compact = false }) {
  if (!indicators) return null

  const items = [
    { label: 'RSI', value: indicators.RSI },
    { label: 'MACD', value: indicators.MACD },
    { label: 'MA5', value: indicators.MA5 },
    { label: 'MA10', value: indicators.MA10 },
    { label: 'MA20', value: indicators.MA20 },
    { label: 'MA Trend', value: indicators.MA_trend },
    { label: 'Volume', value: indicators.volume },
    { label: 'Bollinger', value: indicators.bollinger },
    { label: 'ATR', value: indicators.ATR },
    { label: 'Momentum', value: indicators.momentum },
  ].filter(({ value }) => value !== null && value !== undefined && value !== '')

  if (compact) {
    return (
      <div
        className="grid gap-1 shrink-0"
        style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}
      >
        {items.map(({ label, value }) => (
          <div
            key={label}
            className="bg-terminal-panel border border-terminal-border rounded px-1.5 py-1 min-w-0"
            title={`${label}: ${value}`}
          >
            <p className="text-[11px] text-terminal-muted uppercase truncate">{label}</p>
            <p className="text-[13px] text-gray-200 truncate leading-tight">{value ?? '—'}</p>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
      {items.map(({ label, value }) => (
        <div key={label} className="bg-terminal-panel border border-terminal-border rounded-lg p-3">
          <p className="text-terminal-muted text-[13px] uppercase mb-1">{label}</p>
          <p className="text-sm text-gray-200 truncate">{value ?? '—'}</p>
        </div>
      ))}
    </div>
  )
}
