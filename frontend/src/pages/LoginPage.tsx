import { useNavigate } from 'react-router'
import { writeSession, type Role } from '../auth/session'

const ROLE_ENTRIES: ReadonlyArray<{ role: Role; path: string; label: string }> = [
    { role: 'STUDENT', path: '/student', label: '学生' },
    { role: 'ADMIN', path: '/admin', label: '管理员' },
    { role: 'OPERATOR', path: '/ops', label: '运维' },
]

export default function LoginPage() {
    const navigate = useNavigate()
    const enter = (role: Role, path: string) => {
        writeSession(role)
        navigate(path)
    }
    return (
        <main className="min-h-svh bg-surface px-4 py-8 font-sans text-content">
            <h1 className="text-2xl font-medium text-heading">登录</h1>
            <p className="mt-2 max-w-96">开发桩：选择角色写入本地会话；接入 POST /auth/login（UC-16）后替换为真实表单。</p>
            <div className="mt-6 flex flex-col gap-3">
                {ROLE_ENTRIES.map(({ role, path, label }) => (
                    <button
                        key={role}
                        type="button"
                        className="rounded-md border border-line px-4 py-2"
                        onClick={() => enter(role, path)}
                    >
                        以{label}身份进入
                    </button>
                ))}
            </div>
        </main>
    )
}
