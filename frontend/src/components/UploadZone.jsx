import { useCallback, useState } from 'react'

export default function UploadZone({ onUpload, loading, compact = false }) {
  const [dragOver, setDragOver] = useState(false)

  const handleFile = useCallback(
    (file) => {
      if (!file) return
      const valid = ['image/png', 'image/jpeg', 'image/jpg'].includes(file.type) ||
        /\.(png|jpe?g)$/i.test(file.name)
      if (!valid) {
        alert('Please upload PNG or JPEG image')
        return
      }
      onUpload(file)
    },
    [onUpload],
  )

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleFile(e.dataTransfer.files[0])
  }

  if (compact) {
    return (
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`flex items-center justify-between gap-3 border border-dashed rounded px-3 py-2 transition-colors shrink-0 ${
          dragOver ? 'border-terminal-accent bg-terminal-accent/5' : 'border-terminal-border'
        } ${loading ? 'opacity-50 pointer-events-none' : ''}`}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-lg opacity-60">📊</span>
          <span className="text-[13px] text-gray-400 truncate">Drop Webull / TradingView screenshot</span>
        </div>
        <label className="shrink-0 px-2 py-1 text-[13px] bg-terminal-accent/20 text-terminal-accent border border-terminal-accent/50 rounded cursor-pointer hover:bg-terminal-accent/30">
          Browse
          <input type="file" accept="image/png,image/jpeg,image/jpg" className="hidden" disabled={loading} onChange={(e) => handleFile(e.target.files?.[0])} />
        </label>
      </div>
    )
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      className={`min-h-[400px] w-full max-w-3xl border-2 border-dashed rounded-2xl px-8 py-10 text-center transition-colors flex flex-col items-center justify-center ${
        dragOver ? 'border-terminal-accent bg-terminal-accent/10' : 'border-terminal-accent/70 bg-terminal-panel/60 hover:border-terminal-accent'
      } ${loading ? 'opacity-50 pointer-events-none' : ''}`}
    >
      <div className="text-6xl mb-5 text-terminal-accent">📊</div>
      <p className="text-gray-100 text-[26px] font-bold mb-2">Drop your chart screenshot here</p>
      <p className="text-terminal-muted text-[16px] mb-6">Supports Webull and TradingView screenshots</p>
      <label className="inline-block px-6 py-3 text-[16px] font-semibold bg-terminal-accent/20 text-terminal-accent border border-terminal-accent/70 rounded-lg cursor-pointer hover:bg-terminal-accent/30">
        Browse File
        <input type="file" accept="image/png,image/jpeg,image/jpg" className="hidden" disabled={loading} onChange={(e) => handleFile(e.target.files?.[0])} />
      </label>
      <p className="text-[13px] text-gray-500 mt-5">PNG, JPG, JPEG supported</p>
    </div>
  )
}
