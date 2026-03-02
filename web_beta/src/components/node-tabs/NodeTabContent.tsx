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
}

export function NodeTabContent({ runId, nodeId, tab }: NodeTabContentProps) {
  switch (tab) {
    case 'info':
      return <NodeInfo runId={runId} nodeId={nodeId} />
    case 'logs':
      return <NodeLogs runId={runId} nodeId={nodeId} />
    case 'metrics':
      return <NodeMetrics runId={runId} nodeId={nodeId} />
    case 'images':
      return <NodeImages runId={runId} nodeId={nodeId} />
    case 'audio':
      return <NodeAudio runId={runId} nodeId={nodeId} />
    case 'ask':
      return <NodeAsk runId={runId} nodeId={nodeId} />
  }
}
