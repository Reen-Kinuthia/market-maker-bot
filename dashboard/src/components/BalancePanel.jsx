import { Wallet } from 'lucide-react'

export default function BalancePanel({ balances, symbol, price }) {
  const base = symbol?.split('/')[0] ?? 'BASE'
  const quote = symbol?.split('/')[1] ?? 'QUOTE'

  const baseAmt = balances?.[base] ?? 0
  const quoteAmt = balances?.[quote] ?? 0
  const mid = price?.mid ?? 0

  const baseValue = baseAmt * mid
  const totalValue = baseValue + quoteAmt
  const baseRatio = totalValue > 0 ? (baseValue / totalValue) * 100 : 50

  return (
    <div className="panel">
      <div className="panel-header flex items-center gap-2">
        <Wallet size={10} />
        <span>Balances</span>
      </div>

      <div className="p-3 space-y-3">
        {/* Base */}
        <BalanceRow
          label={base}
          amount={baseAmt}
          value={baseValue}
          color="text-accent-blue"
          decimals={6}
        />
        {/* Quote */}
        <BalanceRow
          label={quote}
          amount={quoteAmt}
          value={quoteAmt}
          color="text-accent-purple"
          decimals={2}
        />

        {/* Portfolio bar */}
        <div className="pt-1">
          <div className="flex justify-between text-[9px] text-gray-600 mb-1">
            <span>{base} {baseRatio.toFixed(1)}%</span>
            <span>{quote} {(100 - baseRatio).toFixed(1)}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-surface-3 overflow-hidden">
            <div
              className="h-full bg-accent-blue rounded-full transition-all duration-500"
              style={{ width: `${baseRatio}%` }}
            />
          </div>
          <div className="text-[9px] text-gray-600 mt-1 text-center">
            Total ≈ ${totalValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
      </div>
    </div>
  )
}

function BalanceRow({ label, amount, value, color, decimals }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <div className={`w-1.5 h-1.5 rounded-full ${color.replace('text-', 'bg-')}`} />
        <span className="text-xs text-gray-400">{label}</span>
      </div>
      <div className="text-right">
        <div className={`text-sm font-semibold ${color} tabular-nums`}>
          {amount.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}
        </div>
        <div className="text-[9px] text-gray-600 tabular-nums">
          ≈ ${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
      </div>
    </div>
  )
}
