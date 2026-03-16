import { useMarketData } from './hooks/useMarketData'
import Header from './components/Header'
import PriceChart from './components/PriceChart'
import OrderDepth from './components/OrderDepth'
import BalancePanel from './components/BalancePanel'
import TradesPanel from './components/TradesPanel'
import StatsBar from './components/StatsBar'
import ReportPanel from './components/ReportPanel'

export default function App() {
  const { data, connected, startBot, stopBot, updateConfig } = useMarketData()

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-surface-0 relative">
      <Header
        data={data}
        connected={connected}
        onStart={startBot}
        onStop={stopBot}
        onConfigSave={updateConfig}
      />

      <StatsBar data={data} />

      <div className="flex flex-1 min-h-0 gap-2 p-2">

        {/* Left column */}
        <div className="flex flex-col gap-2 w-52 shrink-0">
          <BalancePanel
            balances={data?.balances}
            symbol={data?.symbol}
            price={data?.price}
          />
          <ReportPanel stats={data?.stats} symbol={data?.symbol} />
        </div>

        {/* Centre column */}
        <div className="flex flex-col gap-2 flex-1 min-w-0">
          <div className="flex-1 min-h-0" style={{ minHeight: 260 }}>
            <PriceChart priceHistory={data?.price_history} />
          </div>
          <div style={{ height: 210 }}>
            <TradesPanel trades={data?.trades} />
          </div>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-2 w-52 shrink-0">
          <OrderDepth orders={data?.orders} />
        </div>
      </div>

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
