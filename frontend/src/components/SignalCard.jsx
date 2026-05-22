function getSignalStyle(signal, confidence) {
  const c = Number(confidence) || 0

  if (signal === 'BUY') {
    if (c >= 80) {
      return {
        bg: 'bg-emerald-400/25',
        border: 'border-emerald-300',
        text: 'text-emerald-300',
        bar: 'bg-emerald-300',
      }
    }
    if (c >= 65) {
      return {
        bg: 'bg-emerald-500/15',
        border: 'border-emerald-600',
        text: 'text-emerald-500',
        bar: 'bg-emerald-500',
      }
    }
  }

  if (signal === 'SELL' && c >= 65) {
    if (c >= 80) {
      return {
        bg: 'bg-red-400/25',
        border: 'border-red-300',
        text: 'text-red-300',
        bar: 'bg-red-300',
      }
    }
    return {
      bg: 'bg-red-500/20',
      border: 'border-red-500',
      text: 'text-red-400',
      bar: 'bg-red-500',
    }
  }

  return {
    bg: 'bg-amber-500/20',
    border: 'border-amber-500',
    text: 'text-amber-400',
    bar: 'bg-amber-500',
  }
}

export default function SignalCard({ signal, confidence, compact = false, pulse = false }) {
  const style = getSignalStyle(signal, confidence)

  if (compact) {
    return (
      <div className={`rounded-lg border p-2.5 h-full flex flex-col justify-between ${style.bg} ${style.border} ${pulse ? 'signal-pulse' : ''}`}>
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
              className={`h-full rounded-full ${style.bar}`}
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
            className={`h-full rounded-full ${style.bar}`}
            style={{ width: `${confidence}%` }}
          />
        </div>
      </div>
    </div>
  )
}
