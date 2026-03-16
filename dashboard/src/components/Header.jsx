import { Activity, Wifi, WifiOff, Play, Square, Settings } from 'lucide-react'
import { useState } from 'react'

export default function Header({ data, connected, onStart, onStop, onConfigSave }) {
  const [showConfig, setShowConfig] = useState(false)
  const [cfg, setCfg] = useState({
    spread: 0.002,
    levels: 3,
    order_size: 0.001,
    level_spacing: 0.001,
    correlation_weight: 0.7,
  })

  const price = data?.price
  const running = data?.bot_running ?? false
  const symbol = data?.symbol ?? '—'
  const cycle = data?.cycle ?? 0

  const mid = price?.mid ?? 0
  const bid = price?.bid ?? 0
  const ask = price?.ask ?? 0
  const spreadBps = price?.spread_bps ?? 0

  return (
    <header className="panel flex items-center gap-4 px-4 py-2.5 rounded-none border-x-0 border-t-0">
      {/* Logo */}
      <div className="flex items-center gap-2 mr-4">
        <Activity size={18} className="text-accent-blue" />
        <span className="text-sm font-semibold tracking-wider text-white">MM<span className="text-accent-blue">Bot</span></span>
      </div>

      {/* Symbol badge */}
      <div className="flex items-center gap-2 bg-surface-3 rounded px-3 py-1">
        <div className={`w-1.5 h-1.5 rounded-full pulse-dot ${running ? 'bg-accent-green' : 'bg-gray-500'}`} />
        <span className="text-xs font-semibold text-white">{symbol}</span>
      </div>

      {/* Price */}
      <div className="flex items-center gap-6 ml-2">
        <PricePill label="MID" value={mid} color="text-white" size="lg" />
        <PricePill label="BID" value={bid} color="text-accent-green" />
        <PricePill label="ASK" value={ask} color="text-accent-red" />
        <PricePill label="SPREAD" value={`${spreadBps} bps`} color="text-accent-yellow" raw />
      </div>

      <div className="flex-1" />

      {/* Cycle counter */}
      <div className="text-xs text-gray-500 mr-2">
        CYCLE <span className="text-gray-300">{cycle}</span>
      </div>

      {/* Connection */}
      <div className={`flex items-center gap-1.5 text-xs ${connected ? 'text-accent-green' : 'text-accent-red'}`}>
        {connected ? <Wifi size={12} /> : <WifiOff size={12} />}
        <span>{connected ? 'LIVE' : 'DISCONNECTED'}</span>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2 ml-2">
        <button
          onClick={() => setShowConfig(s => !s)}
          className="p-1.5 rounded hover:bg-surface-3 text-gray-500 hover:text-white transition-colors"
        >
          <Settings size={15} />
        </button>
        {running ? (
          <button
            onClick={onStop}
            className="flex items-center gap-1.5 bg-accent-red/10 hover:bg-accent-red/20 border border-accent-red/30 text-accent-red rounded px-3 py-1.5 text-xs font-semibold transition-colors"
          >
            <Square size={11} /> STOP
          </button>
        ) : (
          <button
            onClick={onStart}
            className="flex items-center gap-1.5 bg-accent-green/10 hover:bg-accent-green/20 border border-accent-green/30 text-accent-green rounded px-3 py-1.5 text-xs font-semibold transition-colors"
          >
            <Play size={11} /> START
          </button>
        )}
      </div>

      {/* Config drawer */}
      {showConfig && (
        <div className="absolute top-14 right-4 z-50 panel p-4 w-72 shadow-2xl">
          <div className="panel-header mb-3">Bot Configuration</div>
          <div className="space-y-3">
            {[
              { key: 'spread', label: 'Spread (fraction)', step: 0.0001 },
              { key: 'levels', label: 'Grid Levels', step: 1 },
              { key: 'order_size', label: 'Order Size (base)', step: 0.0001 },
              { key: 'level_spacing', label: 'Level Spacing', step: 0.0001 },
              { key: 'correlation_weight', label: 'Correlation Weight', step: 0.05 },
            ].map(({ key, label, step }) => (
              <div key={key}>
                <label className="text-xs text-gray-500 block mb-1">{label}</label>
                <input
                  type="number"
                  step={step}
                  value={cfg[key]}
                  onChange={e => setCfg(c => ({ ...c, [key]: +e.target.value }))}
                  className="w-full bg-surface-3 border border-surface-4 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-accent-blue"
                />
              </div>
            ))}
            <button
              onClick={() => { onConfigSave(cfg); setShowConfig(false) }}
              className="w-full mt-1 bg-accent-blue/10 hover:bg-accent-blue/20 border border-accent-blue/30 text-accent-blue rounded py-1.5 text-xs font-semibold transition-colors"
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </header>
  )
}

function PricePill({ label, value, color, size = 'sm', raw = false }) {
  const display = raw ? value : (typeof value === 'number' ? value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : value)
  return (
    <div className="flex flex-col">
      <span className="text-[9px] text-gray-600 uppercase tracking-widest">{label}</span>
      <span className={`${size === 'lg' ? 'text-base' : 'text-sm'} font-semibold ${color}`}>{display}</span>
    </div>
  )
}
