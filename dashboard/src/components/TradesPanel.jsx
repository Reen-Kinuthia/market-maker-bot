import { useRef, useEffect } from 'react'
import { ArrowUpRight, ArrowDownRight } from 'lucide-react'

export default function TradesPanel({ trades }) {
  const listRef = useRef(null)
  const prevCountRef = useRef(0)

  // Flash new rows
  useEffect(() => {
    const count = trades?.length ?? 0
    if (count > prevCountRef.current && listRef.current) {
      const rows = listRef.current.querySelectorAll('[data-new="true"]')
      rows.forEach(r => {
        r.removeAttribute('data-new')
      })
    }
    prevCountRef.current = count
  }, [trades])

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header flex items-center justify-between">
        <span>Recent Trades</span>
        <span className="text-gray-600">{trades?.length ?? 0} fills</span>
      </div>

      <div className="overflow-y-auto flex-1" ref={listRef}>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-surface-3 text-[9px] text-gray-600 uppercase tracking-widest">
              <th className="px-3 py-1.5 text-left">Side</th>
              <th className="px-3 py-1.5 text-right">Price</th>
              <th className="px-3 py-1.5 text-right">Size</th>
              <th className="px-3 py-1.5 text-right">Type</th>
              <th className="px-3 py-1.5 text-right">Time</th>
            </tr>
          </thead>
          <tbody>
            {(trades ?? []).map((t) => {
              const isBuy = t.side === 'buy'
              const ts = new Date(t.timestamp * 1000)
              const timeStr = ts.toLocaleTimeString('en-US', { hour12: false })

              return (
                <tr
                  key={t.id}
                  className={`border-b border-surface-2/50 hover:bg-surface-2 transition-colors ${
                    isBuy ? 'flash-green' : 'flash-red'
                  }`}
                >
                  <td className="px-3 py-1">
                    <div className={`flex items-center gap-1 font-semibold ${isBuy ? 'text-accent-green' : 'text-accent-red'}`}>
                      {isBuy ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}
                      {t.side.toUpperCase()}
                    </div>
                  </td>
                  <td className={`px-3 py-1 text-right tabular-nums ${isBuy ? 'text-accent-green' : 'text-accent-red'}`}>
                    {t.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </td>
                  <td className="px-3 py-1 text-right tabular-nums text-gray-300">
                    {t.amount.toFixed(6)}
                  </td>
                  <td className="px-3 py-1 text-right">
                    {t.is_organic
                      ? <span className="text-accent-yellow text-[9px] bg-accent-yellow/10 px-1.5 py-0.5 rounded">ORGANIC</span>
                      : <span className="text-gray-600 text-[9px] bg-surface-3 px-1.5 py-0.5 rounded">MAKER</span>
                    }
                  </td>
                  <td className="px-3 py-1 text-right text-gray-500 tabular-nums">
                    {timeStr}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {(!trades || trades.length === 0) && (
          <div className="text-center text-gray-600 text-xs py-8">Waiting for fills…</div>
        )}
      </div>
    </div>
  )
}
