import { useChat } from '@ai-sdk/react'
import { DefaultChatTransport, type UIMessage } from 'ai'
import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import { ChatComposer } from '@/components/chat/ChatComposer'
import { MessageList } from '@/components/chat/MessageList'
import { env } from '@/lib/env'
import { ApiError } from '@/lib/http'
import { listMessages } from '@/lib/chat'
import { supabase } from '@/lib/supabase'
import { useChatLayout } from '@/pages/chat/chat-layout-context'

function Conversation({ threadId, initialMessages }: { threadId: string; initialMessages: UIMessage[] }) {
  const { refreshThreads } = useChatLayout()
  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: `${env.apiBaseUrl}/chat/stream`,
        prepareSendMessagesRequest: async ({ messages, headers }) => {
          const { data, error } = await supabase.auth.getSession()
          if (error) throw error
          const requestHeaders = new Headers(headers)
          if (data.session) {
            requestHeaders.set(
              'Authorization',
              `Bearer ${data.session.access_token}`,
            )
          }
          return {
            body: { threadId, messages },
            headers: requestHeaders,
          }
        },
      }),
    [threadId],
  )
  const { messages, sendMessage, status, error } = useChat({
    id: threadId,
    messages: initialMessages,
    transport,
    onFinish: () => void refreshThreads(),
  })
  const isStreaming = status === 'submitted' || status === 'streaming'

  return (
    <div className="flex h-full min-h-0 flex-col bg-muted/20">
      <div className="min-h-0 flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="grid h-full place-items-center px-6 text-center">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">What would you like to explore?</h1>
              <p className="mt-2 text-sm text-muted-foreground">Send a message to begin this conversation.</p>
            </div>
          </div>
        ) : (
          <MessageList messages={messages} isStreaming={isStreaming} />
        )}
      </div>
      {error ? <p className="mx-auto w-full max-w-3xl px-4 pb-3 text-sm text-destructive" role="alert">{error.message}</p> : null}
      <ChatComposer disabled={isStreaming} onSend={(text) => sendMessage({ text })} />
    </div>
  )
}

export function ChatThreadPage() {
  const { threadId } = useParams()
  const [history, setHistory] = useState<{
    threadId: string
    messages: UIMessage[] | null
    errorMessage: string | null
  } | null>(null)

  useEffect(() => {
    if (!threadId) return
    let isActive = true
    void listMessages(threadId)
      .then((history) => {
        if (isActive) {
          setHistory({ threadId, messages: history, errorMessage: null })
        }
      })
      .catch((error: unknown) => {
        if (!isActive) return
        setHistory({
          threadId,
          messages: null,
          errorMessage:
            error instanceof ApiError
              ? error.message
              : 'Unable to load this conversation',
        })
      })
    return () => {
      isActive = false
    }
  }, [threadId])

  if (!threadId) return null
  if (history?.threadId !== threadId) {
    return <div className="grid h-full place-items-center text-sm text-muted-foreground">Loading messages…</div>
  }
  if (history.errorMessage) {
    return <div className="grid h-full place-items-center px-6 text-sm text-destructive" role="alert">{history.errorMessage}</div>
  }
  return <Conversation key={threadId} threadId={threadId} initialMessages={history.messages ?? []} />
}
