import { createContext, useContext } from 'react'

import type { ChatThread } from '@/lib/chat'

export interface ChatLayoutContextValue {
  threads: ChatThread[]
  refreshThreads: () => Promise<void>
}

export const ChatLayoutContext = createContext<ChatLayoutContextValue | null>(
  null,
)

export function useChatLayout(): ChatLayoutContextValue {
  const value = useContext(ChatLayoutContext)
  if (value === null) {
    throw new Error('useChatLayout must be used within ChatLayout')
  }
  return value
}
