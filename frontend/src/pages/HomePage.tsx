import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { ApiError } from '@/lib/http'
import { supabase } from '@/lib/supabase'

interface CurrentUserResponse {
  id: string
  email: string | null
}

export function HomePage() {
  const [user, setUser] = useState<CurrentUserResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let isActive = true

    void api
      .get<CurrentUserResponse>('/auth/me')
      .then((currentUser) => {
        if (isActive) setUser(currentUser)
      })
      .catch((error: unknown) => {
        if (!isActive) return
        setErrorMessage(
          error instanceof ApiError ? error.message : 'Authentication check failed',
        )
      })

    return () => {
      isActive = false
    }
  }, [])

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 px-4">
      <section className="w-full max-w-lg rounded-xl border bg-card p-8 shadow-sm">
        <p className="text-sm font-medium text-muted-foreground">Document Copilot</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          Authentication is connected
        </h1>

        {user ? (
          <div className="mt-6 rounded-lg border bg-muted/50 p-4 text-sm">
            <p className="font-medium">Backend token verification succeeded</p>
            <p className="mt-1 text-muted-foreground">{user.email ?? user.id}</p>
          </div>
        ) : errorMessage ? (
          <p className="mt-6 text-sm text-destructive" role="alert">
            {errorMessage}
          </p>
        ) : (
          <p className="mt-6 text-sm text-muted-foreground">
            Verifying your session with the backend…
          </p>
        )}

        <Button
          className="mt-6"
          variant="outline"
          onClick={() => void supabase.auth.signOut()}
        >
          Sign out
        </Button>
      </section>
    </main>
  )
}
