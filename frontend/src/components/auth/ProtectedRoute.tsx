import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '@/lib/auth-context'

export function ProtectedRoute() {
  const { session, isLoading, error } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <main className="grid min-h-svh place-items-center text-sm text-muted-foreground">
        Restoring your session…
      </main>
    )
  }

  if (error) {
    return (
      <main className="grid min-h-svh place-items-center px-4 text-sm text-destructive">
        Unable to restore your session: {error}
      </main>
    )
  }

  if (!session) {
    return (
      <Navigate
        to="/signin"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    )
  }

  return <Outlet />
}
