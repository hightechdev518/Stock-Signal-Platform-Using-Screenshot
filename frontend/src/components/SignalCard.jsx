const SIGNAL_STYLES = {
  BUY: { bg: 'bg-emerald-500/20', border: 'border-emerald-500', text: 'text-emerald-400' },
  SELL: { bg: 'bg-red-500/20', border: 'border-red-500', text: 'text-red-400' },
  HOLD: { bg: 'bg-amber-500/20', border: 'border-amber-500', text: 'text-amber-400' },
}

export default function SignalCard({ signal, confidence, compact = false }) {
  const style = SIGNAL_STYLES[signal] || SIGNAL_STYLES.HOLD

  if (compact) {
    return (
      <div className={`rounded-lg border p-2.5 h-full flex flex-col justify-between ${style.bg} ${style.border}`}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-[12px] text-terminal-muted uppercase">Signal</span>
          <span className={`text-[36px] font-bold leading-none ${style.text}`}>{signal}</span>
        </div>
        <div>
          <div className="flex justify-between text-[13px] mb-0.5">
            <span className="text-gray-500">Confidence</span>
            <span className={`text-[15px] leading-none ${style.text}`}>{confidence}%</span>
          </div>
          <div className="h-1.5 bg-terminal-border rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${signal === 'BUY' ? 'bg-emerald-500' : signal === 'SELL' ? 'bg-red-500' : 'bg-amber-500'}`}
              style={{ width: `${confidence}%` }}
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`rounded-xl border-2 p-6 ${style.bg} ${style.border}`}>
      <p className="text-terminal-muted text-[13px] uppercase mb-1">Signal</p>
      <p className={`text-5xl font-bold ${style.text}`}>{signal}</p>
      <div className="mt-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-400">Confidence</span>
          <span className={style.text}>{confidence}%</span>
        </div>
        <div className="h-2 bg-terminal-border rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${signal === 'BUY' ? 'bg-emerald-500' : signal === 'SELL' ? 'bg-red-500' : 'bg-amber-500'}`}
            style={{ width: `${confidence}%` }}
          />
        </div>
      </div>
    </div>
  )
}
