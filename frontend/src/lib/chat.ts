import type { UIMessage } from 'ai'

import { api } from '@/lib/api'

export interface ChatThread {
  id: string
  userId: string
  title: string
  createdAt: string
  updatedAt: string
}

interface StoredMessage {
  id: string
  threadId: string
  role: UIMessage['role']
  sequenceNumber: number
  content: string
  parts: UIMessage['parts'] | null
  createdAt: string
}

export function listThreads(): Promise<ChatThread[]> {
  return api.get<ChatThread[]>('/chat/threads')
}

export function createThread(title = 'New conversation'): Promise<ChatThread> {
  return api.post<ChatThread>('/chat/threads', { title })
}

export async function listMessages(threadId: string): Promise<UIMessage[]> {
  const messages = await api.get<StoredMessage[]>(
    `/chat/threads/${encodeURIComponent(threadId)}/messages`,
  )

  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    parts:
      message.parts ?? [{ type: 'text' as const, text: message.content }],
  }))
}

export function messageText(message: UIMessage): string {
  return message.parts
    .filter((part) => part.type === 'text')
    .map((part) => part.text)
    .join('')
}
