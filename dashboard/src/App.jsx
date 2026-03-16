import { useMarketData } from './hooks/useMarketData'
import Header from './components/Header'
import PriceChart from './components/PriceChart'
import OrderDepth from './components/OrderDepth'
import BalancePanel from './components/BalancePanel'
import TradesPanel from './components/TradesPanel'
import StatsBar from './components/StatsBar'

export default function App() {
  const { data, connected, startBot, stopBot, updateConfig } = useMarketData()

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-surface-0 relative">
      {/* Top bar */}
      <Header
        data={data}
        connected={connected}
        onStart={startBot}
        onStop={stopBot}
        onConfigSave={updateConfig}
      />

      {/* Stats bar */}
      <StatsBar data={data} />

      {/* Main content */}
      <div className="flex flex-1 min-h-0 gap-2 p-2">

        {/* Left column */}
        <div className="flex flex-col gap-2 w-56 shrink-0">
          <BalancePanel
            balances={data?.balances}
            symbol={data?.symbol}
            price={data?.price}
          />
          <div className="panel flex-1">
            <div className="panel-header">Bot Config</div>
            <ConfigDisplay config={data?.config} />
          </div>
        </div>

        {/* Centre column (chart + trades) */}
        <div className="flex flex-col gap-2 flex-1 min-w-0">
          <div className="flex-1 min-h-0" style={{ minHeight: 260 }}>
            <PriceChart priceHistory={data?.price_history} />
          </div>
          <div style={{ height: 220 }}>
            <TradesPanel trades={data?.trades} />
          </div>
        </div>

        {/* Right column (order depth) */}
        <div className="w-56 shrink-0">
          <OrderDepth orders={data?.orders} />
        </div>
      </div>

      {/* Disconnected overlay */}
      {!connected && (
        <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-40">
          <div className="panel p-6 text-center">
            <div className="text-accent-red text-sm font-semibold mb-1">Disconnected</div>
            <div className="text-gray-500 text-xs">Reconnecting to backend…</div>
          </div>
        </div>
      )}
    </div>
  )
}

function ConfigDisplay({ config }) {
  if (!config) return null
  const rows = [
    ['Symbol', config.symbol],
    ['Spread', `${((config.spread ?? 0) * 100).toFixed(3)}%`],
    ['Levels', config.levels],
    ['Order Size', config.order_size],
    ['Lv. Spacing', config.level_spacing],
    ['Refresh', `${config.refresh_interval}s`],
    ['Corr. Wt.', config.correlation_weight],
    ['Volume Gen', config.volume_generation ? 'ON' : 'OFF'],
  ]
  return (
    <div className="p-3 space-y-1.5">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between items-center">
          <span className="text-[10px] text-gray-600">{k}</span>
          <span className="text-[10px] text-gray-300 tabular-nums">{v}</span>
        </div>
      ))}
    </div>
  )
}
