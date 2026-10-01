import { type ReactNode, useEffect, useState } from 'react'

import { AuthContext, type AuthState } from '@/lib/auth-context'
import { supabase } from '@/lib/supabase'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    session: null,
    isLoading: true,
    error: null,
  })

  useEffect(() => {
    let isActive = true

    void supabase.auth.getSession().then(({ data, error }) => {
      if (!isActive) return
      setState({
        session: data.session,
        isLoading: false,
        error: error?.message ?? null,
      })
    })

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setState({ session, isLoading: false, error: null })
    })

    return () => {
      isActive = false
      data.subscription.unsubscribe()
    }
  }, [])

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>
}
