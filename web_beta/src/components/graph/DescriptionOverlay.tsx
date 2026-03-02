import { useState } from 'react'
import Markdown from 'react-markdown'
import { useStore } from '@/store'
import { cn } from '@/lib/utils'
import { FileText, Minimize2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

interface DescriptionOverlayProps {
  runId: string
}

export function DescriptionOverlay({ runId }: DescriptionOverlayProps) {
  const description = useStore(s => s.runs.get(runId)?.graph?.workflow_description)
  const [expanded, setExpanded] = useState(false)

  if (!description) return null

  const firstLine = description.split('\n')[0].replace(/^#\s*/, '')

  if (!expanded) {
    return (
      <div className="absolute top-3 left-3 z-10">
        <Button
          variant="outline"
          size="sm"
          className="h-8 bg-card/80 backdrop-blur-sm gap-1.5"
          onClick={() => setExpanded(true)}
          title={firstLine}
        >
          <FileText className="h-3.5 w-3.5" />
          <span className="max-w-[180px] truncate text-xs">{firstLine}</span>
        </Button>
      </div>
    )
  }

  return (
    <div className="absolute top-3 left-3 z-10 w-[360px] max-h-[60vh]">
      <div className="bg-card/95 backdrop-blur-sm border border-border rounded-lg shadow-lg flex flex-col max-h-[60vh]">
        <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
          <div className="flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs font-medium">Pipeline Description</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setExpanded(false)}
          >
            <Minimize2 className="h-3.5 w-3.5" />
          </Button>
        </div>
        <ScrollArea className="flex-1 overflow-auto">
          <div className={cn(
            'px-4 py-3 prose prose-sm dark:prose-invert max-w-none',
            'prose-headings:mt-3 prose-headings:mb-1.5 prose-headings:text-sm',
            'prose-p:text-xs prose-p:leading-relaxed prose-p:my-1.5',
            'prose-li:text-xs prose-li:my-0.5',
            'prose-code:text-xs prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded',
            'prose-pre:bg-muted prose-pre:text-xs prose-pre:my-2',
          )}>
            <Markdown>{description}</Markdown>
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
