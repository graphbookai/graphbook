import { useState, useEffect } from 'react'
import { useStore } from '@/store'
import { api } from '@/lib/api'

/**
 * Lazy-load media blob (base64) by mediaId.
 * Returns cached data immediately if available, otherwise fetches on-demand.
 */
export function useMedia(runId: string, mediaId: string): { data: string | null; loading: boolean } {
  const cached = useStore(s => s.mediaCache.get(mediaId))
  const cacheMedia = useStore(s => s.cacheMedia)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (cached || !mediaId) return
    setLoading(true)
    api.getMedia(runId, mediaId)
      .then(res => {
        cacheMedia(mediaId, res.data)
      })
      .catch(() => { /* media not available */ })
      .finally(() => setLoading(false))
  }, [runId, mediaId, cached, cacheMedia])

  return { data: cached ?? null, loading: !cached && loading }
}
