import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { PublicRoute } from '@/components/auth/PublicRoute'
import { AuthProvider } from '@/lib/auth'
import { SignInPage } from '@/pages/SignInPage'
import { SignUpPage } from '@/pages/SignUpPage'
import { ChatLayout } from '@/pages/chat/ChatLayout'
import { ChatListPage } from '@/pages/chat/ChatListPage'
import { ChatThreadPage } from '@/pages/chat/ChatThreadPage'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<PublicRoute />}>
            <Route path="/signin" element={<SignInPage />} />
            <Route path="/signup" element={<SignUpPage />} />
          </Route>
          <Route element={<ProtectedRoute />}>
            <Route index element={<Navigate to="/chats" replace />} />
            <Route path="/chats" element={<ChatLayout />}>
              <Route index element={<ChatListPage />} />
              <Route path=":threadId" element={<ChatThreadPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/chats" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
