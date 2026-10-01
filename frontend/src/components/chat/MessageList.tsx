import type { UIMessage } from 'ai'
import { useEffect, useRef } from 'react'

import { messageText } from '@/lib/chat'
import { cn } from '@/lib/utils'

interface MessageListProps {
  messages: UIMessage[]
  isStreaming: boolean
}

export function MessageList({ messages, isStreaming }: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-8 md:px-8">
      {messages.map((message) => (
        <article
          className={cn(
            'max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6',
            message.role === 'user'
              ? 'ml-auto bg-primary text-primary-foreground'
              : 'border bg-card text-card-foreground shadow-sm',
          )}
          key={message.id}
        >
          <p className="whitespace-pre-wrap">{messageText(message)}</p>
        </article>
      ))}

      {isStreaming ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <span className="size-2 animate-pulse rounded-full bg-current" />
          Document Copilot is responding…
        </div>
      ) : null}
      <div ref={endRef} />
    </div>
  )
}
