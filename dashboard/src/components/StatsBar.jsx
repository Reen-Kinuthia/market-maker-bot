import { TrendingUp, Layers, Zap, RefreshCw } from 'lucide-react'

export default function StatsBar({ data }) {
  const cfg = data?.config ?? {}
  const stats = data?.stats ?? {}
  const price = data?.price ?? {}
  const orders = data?.orders ?? {}

  return (
    <div className="panel flex items-center gap-6 px-4 py-2 flex-wrap">
      <Stat icon={<Layers size={11} />} label="Spread" value={`${((cfg.spread ?? 0.002) * 10000).toFixed(1)} bps`} />
      <Stat icon={<Layers size={11} />} label="Levels" value={cfg.levels ?? 3} />
      <Stat icon={<Zap size={11} />} label="Order Size" value={`${cfg.order_size ?? 0.001} base`} />
      <Stat icon={<TrendingUp size={11} />} label="Corr. Weight" value={`${((cfg.correlation_weight ?? 0.7) * 100).toFixed(0)}%`} />
      <div className="w-px h-6 bg-surface-3" />
      <Stat icon={<RefreshCw size={11} />} label="Open Orders" value={orders.total ?? 0} />
      <Stat icon={<Zap size={11} />} label="Organic" value={stats.organic_orders ?? 0} color="text-accent-yellow" />
      <Stat icon={<TrendingUp size={11} />} label="Ref Mid" value={price.ref_mid ? `$${price.ref_mid?.toLocaleString()}` : '—'} color="text-accent-blue" />
      <div className="ml-auto flex items-center gap-2">
        <span className={`text-[9px] px-2 py-0.5 rounded border ${
          data?.config?.dry_run !== false
            ? 'text-accent-yellow border-accent-yellow/30 bg-accent-yellow/5'
            : 'text-accent-green border-accent-green/30 bg-accent-green/5'
        }`}>
          {data?.config?.dry_run !== false ? '⚠ DRY RUN' : '● LIVE'}
        </span>
      </div>
    </div>
  )
}

function Stat({ icon, label, value, color = 'text-white' }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-gray-600">{icon}</span>
      <div>
        <div className="text-[9px] text-gray-600 uppercase tracking-widest leading-none mb-0.5">{label}</div>
        <div className={`text-xs font-semibold ${color} tabular-nums leading-none`}>{value}</div>
      </div>
    </div>
  )
}
