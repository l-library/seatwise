import { createBrowserRouter, redirect } from 'react-router'
import { readSession } from '../auth/session'
import AdminShell from '../pages/AdminShell'
import LoginPage from '../pages/LoginPage'
import NotFoundPage from '../pages/NotFoundPage'
import OpsShell from '../pages/OpsShell'
import StudentShell from '../pages/StudentShell'

/**
 * 壳路由的 loader 守卫：无会话时抛 redirect('/login')。
 * 抽成纯函数便于单测；不用 route middleware（context 类型推导未经实测）。
 */
export function requireSession(): void {
  if (readSession() === null) throw redirect('/login')
}

export const router = createBrowserRouter([
  { path: '/login', Component: LoginPage },
  {
    path: '/student',
    loader: () => requireSession(),
    Component: StudentShell,
  },
  {
    path: '/admin',
    loader: () => requireSession(),
    Component: AdminShell,
  },
  {
    path: '/ops',
    loader: () => requireSession(),
    Component: OpsShell,
  },
  { path: '*', Component: NotFoundPage },
])
