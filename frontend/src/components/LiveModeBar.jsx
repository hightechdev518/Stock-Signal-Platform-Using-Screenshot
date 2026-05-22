function formatPrice(value) {
  if (value == null || Number.isNaN(value)) return '—'
  const n = Number(value)
  return n >= 1 ? n.toFixed(2) : n.toFixed(4)
}

export default function LiveModeBar({
  liveMode,
  onToggleLiveMode,
  ticker,
  onTickerChange,
  liveActive,
  onStart,
  onStop,
  result,
  priceFlash,
  secondsAgo,
  lastUpdated,
}) {
  return (
    <div className="shrink-0 bg-terminal-panel border border-terminal-border rounded-lg px-3 py-2 flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onToggleLiveMode}
          className={`px-3 py-1.5 rounded-md text-[13px] font-semibold border transition-colors ${
            liveMode
              ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400'
              : 'bg-terminal-bg border-terminal-border text-gray-400 hover:text-gray-200'
          }`}
        >
          {liveMode ? 'LIVE MODE ON' : 'LIVE MODE OFF'}
        </button>

        {liveMode && (
          <>
            <input
              type="text"
              value={ticker}
              onChange={(e) => onTickerChange(e.target.value.toUpperCase())}
              placeholder="Ticker (AAPL, TSLA, SPY)"
              disabled={liveActive}
              className="px-3 py-1.5 rounded-md bg-terminal-bg border border-terminal-border text-gray-100 text-[13px] w-44 uppercase placeholder:normal-case placeholder:text-gray-500 disabled:opacity-60"
            />
            {!liveActive ? (
              <button
                type="button"
                onClick={onStart}
                disabled={!ticker.trim()}
                className="px-3 py-1.5 rounded-md bg-terminal-accent text-terminal-bg text-[13px] font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Start Live Analysis
              </button>
            ) : (
              <button
                type="button"
                onClick={onStop}
                className="px-3 py-1.5 rounded-md bg-red-500/20 border border-red-500/50 text-red-400 text-[13px] font-semibold"
              >
                Stop Live
              </button>
            )}
          </>
        )}
      </div>

      {liveMode && liveActive && result && (
        <div
          className={`flex flex-wrap items-center justify-between gap-3 rounded-md px-3 py-2 border ${
            priceFlash === 'up'
              ? 'live-flash-up border-emerald-500/40'
              : priceFlash === 'down'
                ? 'live-flash-down border-red-500/40'
                : 'border-terminal-border bg-terminal-bg/60'
          }`}
        >
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-emerald-400 text-[12px] font-semibold tracking-wide">LIVE</span>
            </div>
            <div>
              <p className="text-[12px] text-terminal-muted uppercase">{result.ticker}</p>
              <p className="text-[28px] font-bold leading-none text-gray-100">
                ${formatPrice(result.price ?? result.entry_price)}
                <span
                  className={`ml-2 text-[22px] ${
                    result.direction === 'UP'
                      ? 'text-emerald-400'
                      : result.direction === 'DOWN'
                        ? 'text-red-400'
                        : 'text-gray-400'
                  }`}
                >
                  {result.direction === 'UP' ? '↑' : result.direction === 'DOWN' ? '↓' : '→'}
                </span>
              </p>
            </div>
            <p
              className={`text-[15px] font-semibold ${
                (result.change_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
              }`}
            >
              {(result.change_pct ?? 0) >= 0 ? '+' : ''}
              {result.change_pct ?? 0}%
            </p>
          </div>

          <div className="text-right text-[12px] text-terminal-muted">
            <p>Last updated: {lastUpdated || '—'}</p>
            <p>{secondsAgo}s ago</p>
          </div>
        </div>
      )}
    </div>
  )
}
