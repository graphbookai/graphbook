import { useMemo } from 'react'
import { useStore } from '@/store'

export interface ComparisonContext {
  isComparison: boolean
  runIds: string[]
  groupId: string | null
}

export function useComparisonContext(): ComparisonContext {
  const selectedRunId = useStore(s => s.selectedRunId)
  const comparisonGroups = useStore(s => s.comparisonGroups)

  return useMemo(() => {
    if (!selectedRunId) {
      return { isComparison: false, runIds: [], groupId: null }
    }

    if (selectedRunId.startsWith('cmp:')) {
      const group = comparisonGroups.get(selectedRunId)
      if (group) {
        return { isComparison: true, runIds: group.runIds, groupId: selectedRunId }
      }
      return { isComparison: false, runIds: [], groupId: null }
    }

    return { isComparison: false, runIds: [selectedRunId], groupId: null }
  }, [selectedRunId, comparisonGroups])
}
