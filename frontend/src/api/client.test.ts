import { afterEach, expect, test, vi } from 'vitest'
import { ApiError, apiGet, apiPost } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

function stubFetch(res: () => Response) {
  const fetchMock = vi.fn()
  fetchMock.mockImplementation(() => Promise.resolve(res()))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

test('200: 解析 JSON，带 token 时发 Authorization，无 token 时不发', async () => {
  const fetchMock = stubFetch(
    () =>
      new Response(JSON.stringify({ zones: [] }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
  )

  const zones = await apiGet('/zones', { token: 'tok_1' })
  expect(zones).toEqual({ zones: [] })
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toBe('/api/v1/zones')
  expect(new Headers(init.headers).get('authorization')).toBe('Bearer tok_1')

  await apiGet('/zones')
  const [, secondInit] = fetchMock.mock.calls[1] as unknown as [string, RequestInit]
  expect(new Headers(secondInit.headers).get('authorization')).toBeNull()
})

test('problem+json 错误体映射为带 code 与 trace_id 的 ApiError', async () => {
  stubFetch(
    () =>
      new Response(
        JSON.stringify({
          type: 'https://seatwise.local/problems/seat-taken',
          title: '该座位刚被占用',
          status: 409,
          code: 'SEAT_TAKEN',
          detail: '座位已被预约',
          trace_id: '4b1c9f2e8a7d',
        }),
        { status: 409, headers: { 'content-type': 'application/problem+json' } },
      ),
  )

  let thrown: unknown
  try {
    await apiGet('/zones')
  } catch (error) {
    thrown = error
  }
  expect(thrown).toBeInstanceOf(ApiError)
  const apiError = thrown as ApiError
  expect(apiError.status).toBe(409)
  expect(apiError.code).toBe('SEAT_TAKEN')
  expect(apiError.title).toBe('该座位刚被占用')
  expect(apiError.trace_id).toBe('4b1c9f2e8a7d')
})

/** 204 响应无法用真实 Response 携带非法残体（构造器对 null-body 状态抛 TypeError），
 * 用最小假体模拟违规网关：带 json content-type 且残留无法解析的载荷。 */
function fakeResponse(status: number, contentType: string, text: string): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': contentType }),
    text: () => Promise.resolve(text),
  } as unknown as Response
}

test('204 与空体返回 undefined，Idempotency-Key 由调用方显式传入', async () => {
  const fetchMock = stubFetch(() => new Response(null, { status: 204 }))

  const result = await apiPost('/auth/logout', undefined, { idempotencyKey: 'key-7' })
  expect(result).toBeUndefined()
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toBe('/api/v1/auth/logout')
  expect(new Headers(init.headers).get('idempotency-key')).toBe('key-7')
})

test('401 触发 onUnauthorized 回调并抛 ApiError', async () => {
  stubFetch(
    () =>
      new Response(
        JSON.stringify({
          type: 'about:blank',
          title: '未认证',
          status: 401,
          code: 'UNAUTHENTICATED',
          detail: '令牌缺失或过期',
          trace_id: 'a1b2c3',
        }),
        { status: 401, headers: { 'content-type': 'application/problem+json' } },
      ),
  )
  const onUnauthorized = vi.fn()

  await expect(apiGet('/auth/me', { onUnauthorized })).rejects.toBeInstanceOf(ApiError)
  expect(onUnauthorized).toHaveBeenCalledOnce()
})

test('204 带 json content-type 与残体时返回 undefined，不尝试 JSON 解析', async () => {
  stubFetch(() => fakeResponse(204, 'application/json', 'NO_CONTENT'))

  const result = await apiPost('/auth/logout', undefined, { idempotencyKey: 'key-204' })
  expect(result).toBeUndefined()
})
