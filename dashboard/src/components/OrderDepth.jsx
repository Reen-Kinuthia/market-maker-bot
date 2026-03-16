export default function OrderDepth({ orders }) {
  const bids = orders?.bids ?? []
  const asks = orders?.asks ?? []

  const allSizes = [...bids, ...asks].map(o => o.amount)
  const maxSize = Math.max(...allSizes, 0.001)

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header flex items-center justify-between">
        <span>Order Depth</span>
        <span className="text-gray-600">{orders?.total ?? 0} orders</span>
      </div>

      <div className="flex flex-col h-full overflow-hidden">
        {/* Column headers */}
        <div className="flex justify-between px-3 py-1 text-[9px] text-gray-600 uppercase tracking-widest border-b border-surface-2">
          <span>Price</span>
          <span>Size / Fill</span>
        </div>

        {/* Asks reversed */}
        <div className="flex-1 overflow-y-auto flex flex-col-reverse px-3 pt-1">
          {asks.map((o) => (
            <OrderRow key={o.id} order={o} side="sell" maxSize={maxSize} />
          ))}
        </div>

        {/* Spread indicator */}
        <div className="border-y border-surface-3 py-1.5 px-3 text-center bg-surface-2/30">
          <span className="text-[9px] text-gray-600 tracking-widest uppercase">
            Spread&nbsp;
            {bids[0] && asks[0]
              ? `${(asks[0].price - bids[0].price).toFixed(2)}`
              : '—'}
          </span>
        </div>

        {/* Bids */}
        <div className="flex-1 overflow-y-auto px-3 pb-1">
          {bids.map((o) => (
            <OrderRow key={o.id} order={o} side="buy" maxSize={maxSize} />
          ))}
        </div>
      </div>
    </div>
  )
}

function OrderRow({ order, side, maxSize }) {
  const depthPct = Math.min(100, (order.amount / maxSize) * 100)
  const fillPct  = order.fill_pct ?? 0
  const isBuy = side === 'buy'
  const depthColor = isBuy ? 'rgba(0,212,160,0.10)' : 'rgba(255,77,106,0.10)'
  const fillColor  = isBuy ? 'rgba(0,212,160,0.28)' : 'rgba(255,77,106,0.28)'
  const textColor  = isBuy ? 'text-accent-green' : 'text-accent-red'

  const badge = order.is_organic
    ? <span className="ml-1 text-[8px] text-accent-yellow px-1 rounded bg-accent-yellow/10">ORG</span>
    : null

  return (
    <div className="relative flex items-center justify-between py-[3px] text-xs font-mono hover:bg-surface-3/40 transition-colors cursor-default overflow-hidden">
      {/* Depth background bar */}
      <div className="absolute inset-y-0 right-0 pointer-events-none" style={{ width: `${depthPct}%`, background: depthColor }} />
      {/* Fill overlay bar */}
      {fillPct > 0 && (
        <div className="absolute inset-y-0 right-0 pointer-events-none transition-all duration-300" style={{ width: `${depthPct * fillPct / 100}%`, background: fillColor }} />
      )}

      {/* Price */}
      <span className={`z-10 ${textColor} tabular-nums w-24 text-[11px]`}>
        {order.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>

      {/* Size + fill bar */}
      <div className="z-10 flex flex-col items-end">
        <span className="text-gray-400 tabular-nums text-[10px]">
          {order.amount.toFixed(5)}{badge}
        </span>
        {fillPct > 0 && (
          <div className="flex items-center gap-1 mt-0.5">
            <div className="h-0.5 rounded-full bg-surface-3 w-12 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${isBuy ? 'bg-accent-green' : 'bg-accent-red'}`}
                style={{ width: `${fillPct}%` }}
              />
            </div>
            <span className={`text-[8px] tabular-nums ${isBuy ? 'text-accent-green' : 'text-accent-red'}`}>
              {fillPct.toFixed(0)}%
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
