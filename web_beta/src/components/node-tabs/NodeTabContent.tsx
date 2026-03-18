import type { NodeTab } from '@/store'
import { NodeInfo } from './NodeInfo'
import { NodeLogs } from './NodeLogs'
import { NodeMetrics } from './NodeMetrics'
import { NodeImages } from './NodeImages'
import { NodeAudio } from './NodeAudio'
import { NodeAsk } from './NodeAsk'

interface NodeTabContentProps {
  runId: string
  nodeId: string
  tab: NodeTab
  comparisonRunIds?: string[]
}

export function NodeTabContent({ runId, nodeId, tab, comparisonRunIds }: NodeTabContentProps) {
  switch (tab) {
    case 'info':
      return <NodeInfo runId={runId} nodeId={nodeId} comparisonRunIds={comparisonRunIds} />
    case 'logs':
      return <NodeLogs runId={runId} nodeId={nodeId} comparisonRunIds={comparisonRunIds} />
    case 'metrics':
      return <NodeMetrics runId={runId} nodeId={nodeId} comparisonRunIds={comparisonRunIds} />
    case 'images':
      return <NodeImages runId={runId} nodeId={nodeId} comparisonRunIds={comparisonRunIds} />
    case 'audio':
      return <NodeAudio runId={runId} nodeId={nodeId} comparisonRunIds={comparisonRunIds} />
    case 'ask':
      return <NodeAsk runId={runId} nodeId={nodeId} />
  }
}
