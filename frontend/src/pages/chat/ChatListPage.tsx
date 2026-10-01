import { MessageSquareText } from 'lucide-react'

export function ChatListPage() {
  return (
    <div className="grid h-full place-items-center px-6 text-center">
      <div className="max-w-md">
        <MessageSquareText className="mx-auto size-10 text-muted-foreground" />
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">Start a conversation</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Create a new conversation or choose one from the sidebar to continue your research.
        </p>
      </div>
    </div>
  )
}
