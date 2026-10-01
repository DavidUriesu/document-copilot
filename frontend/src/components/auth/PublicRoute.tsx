import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '@/lib/auth-context'

export function PublicRoute() {
  const { session, isLoading } = useAuth()

  if (isLoading) {
    return (
      <main className="grid min-h-svh place-items-center text-sm text-muted-foreground">
        Restoring your session…
      </main>
    )
  }

  return session ? <Navigate to="/" replace /> : <Outlet />
}
