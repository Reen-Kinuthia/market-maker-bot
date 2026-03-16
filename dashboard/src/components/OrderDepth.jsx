export default function OrderDepth({ orders }) {
  const bids = orders?.bids ?? []
  const asks = orders?.asks ?? []

  const allSizes = [...bids, ...asks].map(o => o.amount)
  const maxSize = Math.max(...allSizes, 0.001)

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header flex items-center justify-between">
        <span>Order Depth</span>
        <span className="text-gray-600">{(orders?.total ?? 0)} orders</span>
      </div>

      <div className="flex flex-col h-full overflow-hidden p-0">
        {/* Asks (top = highest) */}
        <div className="flex-1 overflow-y-auto flex flex-col-reverse px-3 pt-2">
          {asks.map((o) => (
            <OrderRow key={o.id} order={o} side="sell" maxSize={maxSize} />
          ))}
        </div>

        {/* Spread indicator */}
        <div className="border-y border-surface-3 py-1.5 px-3 text-center">
          <span className="text-[9px] text-gray-600 tracking-widest uppercase">
            Spread&nbsp;
            {bids[0] && asks[0]
              ? `${(asks[0].price - bids[0].price).toFixed(2)}`
              : '—'}
          </span>
        </div>

        {/* Bids (top = highest) */}
        <div className="flex-1 overflow-y-auto px-3 pb-2">
          {bids.map((o) => (
            <OrderRow key={o.id} order={o} side="buy" maxSize={maxSize} />
          ))}
        </div>
      </div>
    </div>
  )
}

function OrderRow({ order, side, maxSize }) {
  const pct = Math.min(100, (order.amount / maxSize) * 100)
  const isBuy = side === 'buy'
  const barColor = isBuy ? 'rgba(0,212,160,0.12)' : 'rgba(255,77,106,0.12)'
  const textColor = isBuy ? 'text-accent-green' : 'text-accent-red'
  const badge = order.is_organic ? (
    <span className="ml-1 text-[8px] text-accent-yellow px-1 rounded bg-accent-yellow/10">ORG</span>
  ) : null

  return (
    <div
      className="relative flex items-center justify-between py-0.5 px-0 text-xs font-mono hover:bg-surface-3/50 transition-colors cursor-default"
      style={{ overflow: 'hidden' }}
    >
      {/* depth bar */}
      <div
        className="absolute inset-y-0 right-0 pointer-events-none"
        style={{ width: `${pct}%`, background: barColor }}
      />
      <span className={`z-10 ${textColor} tabular-nums w-24`}>
        {order.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
      <span className="z-10 text-gray-400 tabular-nums">
        {order.amount.toFixed(6)}{badge}
      </span>
    </div>
  )
}
