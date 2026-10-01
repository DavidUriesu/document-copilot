import { LogOut, MessageSquare, Plus } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import type { ChatThread } from '@/lib/chat'
import { supabase } from '@/lib/supabase'
import { cn } from '@/lib/utils'

interface ThreadSidebarProps {
  threads: ChatThread[]
  isCreating: boolean
  onCreate: () => void
}

export function ThreadSidebar({
  threads,
  isCreating,
  onCreate,
}: ThreadSidebarProps) {
  return (
    <aside className="flex h-full w-full flex-col border-r bg-muted/40 md:w-72">
      <div className="border-b p-4">
        <p className="text-sm font-semibold tracking-tight">Document Copilot</p>
        <p className="mt-1 text-xs text-muted-foreground">Research conversations</p>
        <Button
          className="mt-4 w-full justify-start"
          disabled={isCreating}
          onClick={onCreate}
        >
          <Plus />
          {isCreating ? 'Creating…' : 'New conversation'}
        </Button>
      </div>

      <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2" aria-label="Conversations">
        {threads.length === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-muted-foreground">
            No conversations yet.
          </p>
        ) : (
          threads.map((thread) => (
            <NavLink
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors hover:bg-muted',
                  isActive && 'bg-muted font-medium',
                )
              }
              key={thread.id}
              to={`/chats/${thread.id}`}
            >
              <MessageSquare className="size-4 shrink-0 text-muted-foreground" />
              <span className="truncate">{thread.title}</span>
            </NavLink>
          ))
        )}
      </nav>

      <div className="border-t p-2">
        <Button
          className="w-full justify-start"
          variant="ghost"
          onClick={() => void supabase.auth.signOut()}
        >
          <LogOut />
          Sign out
        </Button>
      </div>
    </aside>
  )
}
