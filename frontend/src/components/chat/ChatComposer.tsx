import { ArrowUp } from 'lucide-react'
import { type FormEvent, type KeyboardEvent, useState } from 'react'

import { Button } from '@/components/ui/button'

interface ChatComposerProps {
  disabled: boolean
  onSend: (text: string) => Promise<void>
}

export function ChatComposer({ disabled, onSend }: ChatComposerProps) {
  const [input, setInput] = useState('')

  async function submit() {
    const text = input.trim()
    if (!text || disabled) return
    setInput('')
    await onSend(text)
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void submit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void submit()
    }
  }

  return (
    <form className="mx-auto flex w-full max-w-3xl gap-2 px-4 pb-5 md:px-8" onSubmit={handleSubmit}>
      <textarea
        aria-label="Message"
        className="min-h-12 max-h-40 flex-1 resize-y rounded-xl border bg-background px-4 py-3 text-sm shadow-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
        disabled={disabled}
        onChange={(event) => setInput(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about your documents…"
        rows={1}
        value={input}
      />
      <Button
        aria-label="Send message"
        className="size-12 rounded-xl"
        disabled={disabled || input.trim() === ''}
        size="icon-lg"
        type="submit"
      >
        <ArrowUp />
      </Button>
    </form>
  )
}
