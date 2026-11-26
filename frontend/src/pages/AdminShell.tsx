import { Link, Outlet } from 'react-router'
import { readSession } from '../auth/session'
import ForbiddenPage from './ForbiddenPage'

/** 角色壳骨架：dev 会话不匹配时显示 403，匹配时留出 <Outlet/> 给子路由。 */
export default function AdminShell() {
    if (readSession() !== 'ADMIN') return <ForbiddenPage />
    return (
        <main className="min-h-svh bg-surface px-4 py-8 font-sans text-content">
            <h1 className="text-2xl font-medium text-heading">管理端</h1>
            <p className="mt-2 max-w-96">骨架页：政策配置、预约管理等业务页面在后续 PR 落地。</p>
            <nav className="mt-6 flex gap-4">
                <Link className="text-brand underline" to="/login">
                    切换角色（回登录页）
                </Link>
            </nav>
            <Outlet />
        </main>
    )
}
