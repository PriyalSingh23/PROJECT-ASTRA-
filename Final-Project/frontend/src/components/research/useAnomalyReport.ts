import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../services/api'
import { AnomalyReport } from '../../types'

/**
 * Polls the consolidated integrity endpoint.
 *
 * The endpoint is the single honest source for both the model panel and the
 * anomaly strip, so both surfaces share one hook rather than fetching twice.
 */
export function useAnomalyReport(refreshMs: number = 30000) {
  const [report, setReport] = useState<AnomalyReport | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<number | null>(null)
  const cancelled = useRef<boolean>(false)

  const refresh = useCallback(async () => {
    try {
      const res = await api.getAnomalies()
      if (!cancelled.current) {
        setReport(res)
        setError(null)
        setLastUpdated(Date.now())
      }
    } catch (err: any) {
      if (!cancelled.current) setError(err?.message || 'Integrity endpoint unreachable')
    } finally {
      if (!cancelled.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    cancelled.current = false
    refresh()
    if (!refreshMs) {
      return () => {
        cancelled.current = true
      }
    }
    const id = window.setInterval(refresh, refreshMs)
    return () => {
      cancelled.current = true
      window.clearInterval(id)
    }
  }, [refresh, refreshMs])

  return { report, loading, error, lastUpdated, refresh }
}
