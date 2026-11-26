import { Link } from 'react-router'

export default function ForbiddenPage() {
    return (
        <main className="min-h-svh bg-surface px-4 py-8 font-sans text-content">
            <h1 className="text-2xl font-medium text-heading">403</h1>
            <p className="mt-2 max-w-96">当前角色无权访问该区域。</p>
            <nav className="mt-6">
                <Link className="text-brand underline" to="/login">
                    回登录页
                </Link>
            </nav>
        </main>
    )
}
