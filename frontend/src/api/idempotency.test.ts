import { expect, test } from 'vitest'
import { newIdempotencyKey } from './idempotency'

test('newIdempotencyKey 生成 UUID v7（第 13 位是 7，变体位在 8/9/a/b）', () => {
  const key = newIdempotencyKey()
  expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
})

test('前 48 位是当前毫秒时间戳，满足幂等键的时序语义（API.md 1.6）', () => {
  const key = newIdempotencyKey()
  const timestamp = Number.parseInt(key.slice(0, 13).replace('-', ''), 16)
  expect(Math.abs(timestamp - Date.now())).toBeLessThan(5_000)
})
