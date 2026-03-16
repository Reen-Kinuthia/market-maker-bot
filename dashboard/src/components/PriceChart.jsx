import { useEffect, useRef } from 'react'
import { createChart } from 'lightweight-charts'

export default function PriceChart({ priceHistory }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const midSeriesRef = useRef(null)
  const refSeriesRef = useRef(null)
  const bidSeriesRef = useRef(null)
  const askSeriesRef = useRef(null)

  // Init chart
  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#0d1117' },
        textColor: '#64748b',
      },
      grid: {
        vertLines: { color: '#1a2332' },
        horzLines: { color: '#1a2332' },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: '#3b9eff44', labelBackgroundColor: '#131920' },
        horzLine: { color: '#3b9eff44', labelBackgroundColor: '#131920' },
      },
      rightPriceScale: { borderColor: '#1a2332' },
      timeScale: {
        borderColor: '#1a2332',
        timeVisible: true,
        secondsVisible: true,
      },
      handleScroll: true,
      handleScale: true,
    })

    const midSeries = chart.addLineSeries({
      color: '#e2e8f0',
      lineWidth: 2,
      title: 'Mid',
      priceLineVisible: false,
      lastValueVisible: true,
    })

    const refSeries = chart.addLineSeries({
      color: '#3b9eff88',
      lineWidth: 1,
      lineStyle: 2, // dashed
      title: 'Ref',
      priceLineVisible: false,
      lastValueVisible: false,
    })

    const bidSeries = chart.addLineSeries({
      color: '#00d4a066',
      lineWidth: 1,
      title: 'Bid',
      priceLineVisible: false,
      lastValueVisible: false,
    })

    const askSeries = chart.addLineSeries({
      color: '#ff4d6a66',
      lineWidth: 1,
      title: 'Ask',
      priceLineVisible: false,
      lastValueVisible: false,
    })

    chartRef.current = chart
    midSeriesRef.current = midSeries
    refSeriesRef.current = refSeries
    bidSeriesRef.current = bidSeries
    askSeriesRef.current = askSeries

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [])

  // Update data
  useEffect(() => {
    if (!priceHistory?.length) return
    if (!midSeriesRef.current) return

    const toPoint = (p, key) => ({
      time: Math.floor(p.t),
      value: p[key],
    })

    const dedupe = (arr) => {
      const seen = new Set()
      return arr.filter(p => {
        if (seen.has(p.time)) return false
        seen.add(p.time)
        return true
      }).sort((a, b) => a.time - b.time)
    }

    midSeriesRef.current.setData(dedupe(priceHistory.map(p => toPoint(p, 'mid'))))
    refSeriesRef.current.setData(dedupe(priceHistory.map(p => toPoint(p, 'ref'))))
    bidSeriesRef.current.setData(dedupe(priceHistory.map(p => toPoint(p, 'bid'))))
    askSeriesRef.current.setData(dedupe(priceHistory.map(p => toPoint(p, 'ask'))))
  }, [priceHistory])

  return (
    <div className="panel flex flex-col h-full">
      <div className="panel-header flex items-center justify-between">
        <span>Price Chart</span>
        <div className="flex items-center gap-4 text-[9px]">
          <Legend color="#e2e8f0" label="Mid" />
          <Legend color="#3b9eff" label="Ref Exchange" dashed />
          <Legend color="#00d4a0" label="Bid" />
          <Legend color="#ff4d6a" label="Ask" />
        </div>
      </div>
      <div ref={containerRef} className="flex-1 min-h-0" />
    </div>
  )
}

function Legend({ color, label, dashed }) {
  return (
    <div className="flex items-center gap-1.5">
      <div
        className="w-4 h-px"
        style={{ background: color, borderTop: dashed ? `1px dashed ${color}` : undefined }}
      />
      <span style={{ color }}>{label}</span>
    </div>
  )
}
