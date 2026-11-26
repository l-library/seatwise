/**
 * 手写 UUID v7：crypto.randomUUID() 只产 v4，不满足 API.md 1.6
 * 「同一逻辑操作重试间复用」对幂等键的时序语义。约 10 行，不引依赖。
 */
export function newIdempotencyKey(): string {
    const bytes = crypto.getRandomValues(new Uint8Array(16))
    const ts = Date.now()
    bytes[0] = Math.floor(ts / 2 ** 40)
    bytes[1] = Math.floor(ts / 2 ** 32) & 0xff
    bytes[2] = Math.floor(ts / 2 ** 24) & 0xff
    bytes[3] = Math.floor(ts / 2 ** 16) & 0xff
    bytes[4] = Math.floor(ts / 2 ** 8) & 0xff
    bytes[5] = ts & 0xff
    bytes[6] = (bytes[6] & 0x0f) | 0x70 // version 7
    bytes[8] = (bytes[8] & 0x3f) | 0x80 // RFC 4122 variant
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
