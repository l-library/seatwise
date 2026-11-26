/**
 * dev-only 会话桩，集中在此一个文件。
 * 接入 POST /auth/login（UC-16）后，这里是唯一替换点。
 * Role 枚举以 docs/openapi.yaml 的 components.schemas.Role 为准。
 */
export type Role = 'STUDENT' | 'ADMIN' | 'OPERATOR'

const STORAGE_KEY = 'seatwise.dev-session'

export function readSession(): Role | null {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw === 'STUDENT' || raw === 'ADMIN' || raw === 'OPERATOR' ? raw : null
}

export function writeSession(role: Role): void {
    localStorage.setItem(STORAGE_KEY, role)
}

export function clearSession(): void {
    localStorage.removeItem(STORAGE_KEY)
}
