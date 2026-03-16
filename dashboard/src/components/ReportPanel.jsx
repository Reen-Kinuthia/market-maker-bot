import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

function fmt(n, decimals = 2) {
  if (n === undefined || n === null) return '—'
  return Number(n).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function fmtTime(s) {
  if (!s) return '—'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${sec}s`
  return `${sec}s`
}

export default function ReportPanel({ stats, symbol }) {
  if (!stats) return null

  const pnl = stats.pnl ?? 0
  const pnlPct = stats.pnl_pct ?? 0
  const pnlPos = pnl >= 0

  const fillRate = stats.fill_rate_per_min ?? 0
  const makerFills = stats.maker_fills ?? 0
  const organicFills = stats.organic_fills ?? 0
  const totalFills = stats.total_fills ?? 0
  const organicPct = totalFills > 0 ? ((organicFills / totalFills) * 100).toFixed(0) : 0

  return (
    <div className="panel">
      <div className="panel-header">Report</div>
      <div className="p-3 space-y-0.5">

        {/* PnL — hero stat */}
        <div className="flex items-center justify-between py-2 border-b border-surface-3 mb-2">
          <span className="text-[10px] text-gray-500">Unrealised PnL</span>
          <div className="flex items-center gap-1.5">
            {pnlPos
              ? <TrendingUp size={11} className="text-accent-green" />
              : pnl === 0
              ? <Minus size={11} className="text-gray-500" />
              : <TrendingDown size={11} className="text-accent-red" />
            }
            <span className={`text-sm font-semibold tabular-nums ${pnlPos ? 'text-accent-green' : pnl === 0 ? 'text-gray-400' : 'text-accent-red'}`}>
              {pnlPos ? '+' : ''}{fmt(pnl)}
            </span>
            <span className={`text-[9px] tabular-nums ${pnlPos ? 'text-accent-green/70' : 'text-accent-red/70'}`}>
              ({pnlPos ? '+' : ''}{fmt(pnlPct, 3)}%)
            </span>
          </div>
        </div>

        <Row label="Portfolio Value"   value={`$${fmt(stats.portfolio_value)}`} />
        <Row label="Spread Revenue"    value={`$${fmt(stats.spread_revenue, 4)}`} color="text-accent-green" />

        <div className="my-1 border-t border-surface-2" />

        <Row label="Total Fills"       value={totalFills} />
        <Row label="Maker Fills"       value={makerFills} />
        <Row label="Organic Fills"     value={`${organicFills} (${organicPct}%)`} color="text-accent-yellow" />
        <Row label="Fill Rate"         value={`${fmt(fillRate, 1)}/min`} />

        <div className="my-1 border-t border-surface-2" />

        <Row label="Total Volume"      value={`${fmt(stats.total_volume, 5)} ${symbol?.split('/')[0] ?? ''}`} />
        <Row label="Buy Volume"        value={fmt(stats.buy_volume,  5)} color="text-accent-green" />
        <Row label="Sell Volume"       value={fmt(stats.sell_volume, 5)} color="text-accent-red"   />

        <div className="my-1 border-t border-surface-2" />

        <Row label="Uptime"            value={fmtTime(stats.uptime_s)} />
      </div>
    </div>
  )
}

function Row({ label, value, color = 'text-gray-200' }) {
  return (
    <div className="flex items-center justify-between py-[3px]">
      <span className="text-[10px] text-gray-600">{label}</span>
      <span className={`text-[11px] font-medium tabular-nums ${color}`}>{value}</span>
    </div>
  )
}
