import { useCallback, useEffect, useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'

import { ThreadSidebar } from '@/components/chat/ThreadSidebar'
import { createThread, listThreads, type ChatThread } from '@/lib/chat'
import { ApiError } from '@/lib/http'
import { ChatLayoutContext } from '@/pages/chat/chat-layout-context'

export function ChatLayout() {
  const navigate = useNavigate()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const refreshThreads = useCallback(async () => {
    try {
      const nextThreads = await listThreads()
      setThreads(nextThreads)
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : 'Unable to refresh conversations',
      )
    }
  }, [])

  useEffect(() => {
    let isActive = true
    void listThreads()
      .then((nextThreads) => {
        if (isActive) setThreads(nextThreads)
      })
      .catch((error: unknown) => {
        if (!isActive) return
        setErrorMessage(error instanceof ApiError ? error.message : 'Unable to load conversations')
      })
      .finally(() => {
        if (isActive) setIsLoading(false)
      })
    return () => {
      isActive = false
    }
  }, [])

  async function handleCreate() {
    setErrorMessage(null)
    setIsCreating(true)
    try {
      const thread = await createThread()
      setThreads((current) => [thread, ...current])
      navigate(`/chats/${thread.id}`)
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : 'Unable to create a conversation')
    } finally {
      setIsCreating(false)
    }
  }

  if (isLoading) {
    return <main className="grid min-h-svh place-items-center text-sm text-muted-foreground">Loading conversations…</main>
  }

  return (
    <ChatLayoutContext.Provider value={{ threads, refreshThreads }}>
      <main className="grid h-svh grid-rows-[auto_1fr] overflow-hidden md:grid-cols-[18rem_1fr] md:grid-rows-1">
        <div className="max-h-64 md:max-h-none">
          <ThreadSidebar threads={threads} isCreating={isCreating} onCreate={() => void handleCreate()} />
        </div>
        <section className="min-h-0 min-w-0">
          {errorMessage ? (
            <p className="border-b bg-destructive/10 px-4 py-2 text-sm text-destructive" role="alert">{errorMessage}</p>
          ) : null}
          <Outlet />
        </section>
      </main>
    </ChatLayoutContext.Provider>
  )
}
