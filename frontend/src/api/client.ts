import type { components, paths } from './schema'

/**
 * 裸 fetch 封装。基址与 docs/openapi.yaml 的 servers 声明一致（/api/v1）。
 * spec 中连 /auth/login、/health 都标了 bearerAuth，那是契约缺陷；
 * 封装按「有 token 才发 Authorization」实现。
 */
const BASE_PATH = '/api/v1'

/** RFC 9457 problem+json（spec Problem schema）映射出的类型化错误。 */
export class ApiError extends Error {
    readonly status: number
    readonly code: components['schemas']['ErrorCode'] | undefined
    readonly title: string
    readonly type: string | undefined
    readonly detail: string | undefined
    readonly trace_id: string | undefined

    constructor(init: {
        status: number
        title: string
        code?: components['schemas']['ErrorCode']
        type?: string
        detail?: string
        trace_id?: string
    }) {
        super(`${init.status} ${init.title}${init.code ? ` (${init.code})` : ''}`)
        this.name = 'ApiError'
        this.status = init.status
        this.code = init.code
        this.title = init.title
        this.type = init.type
        this.detail = init.detail
        this.trace_id = init.trace_id
    }
}

type Method = 'get' | 'post' | 'patch' | 'delete'

/** 某个方法可用的 path 模板集合；用 GET 调 POST-only 路径在编译期报错。 */
type PathOf<M extends Method> = {
    [P in keyof paths]: paths[P][M] extends undefined ? never : P
}[keyof paths]

/** 从 paths 提取某个 path 的操作类型；不支持则为 never，让错误调用在编译期失败。 */
type Operation<P extends keyof paths, M extends Method> =
    paths[P] extends { [K in M]: infer Op } ? (Op extends undefined ? never : Op) : never

/** 请求体类型；无请求体的端点为 undefined。 */
type RequestBody<Op> =
    Op extends { requestBody: { content: { 'application/json': infer Body } } } ? Body : undefined

/**
 * 成功（2xx）响应体类型。只有 204 的端点（如 POST /auth/logout）落到 undefined，
 * 不会索引到 never。
 */
type SuccessBody<Op> =
    Op extends { responses: { 200: { content: { 'application/json': infer Body } } } } ? Body
    : Op extends { responses: { 201: { content: { 'application/json': infer Body } } } } ? Body
    : undefined

/**
 * Idempotency-Key 必须由调用方显式传入（API.md 1.6：同一逻辑操作重试间复用），
 * 封装不自动生成。spec 里要求该头的操作为必填，其余可选。
 */
type IdempotencyOptions<Op> =
    Op extends { parameters: { header: { 'Idempotency-Key': string } } }
        ? { idempotencyKey: string }
        : { idempotencyKey?: string }

interface RequestOptions {
    token?: string
    /** 路径参数，替换 path 里的 {placeholder}；刻意保持松类型，不做逐段泛型替换。 */
    pathParams?: Record<string, string>
    query?: Record<string, string>
    /** 401 时回调（如跳登录）；封装不 import router，避免循环依赖。 */
    onUnauthorized?: () => void
}

function buildUrl(path: string, opts: RequestOptions): string {
    const filled = opts.pathParams
        ? path.replace(/\{([^{}]+)\}/g, (placeholder, key: string) => opts.pathParams?.[key] ?? placeholder)
        : path
    const search = opts.query ? new URLSearchParams(opts.query).toString() : ''
    return `${BASE_PATH}${filled}${search === '' ? '' : `?${search}`}`
}

function isProblem(value: unknown): value is components['schemas']['Problem'] {
    return (
        typeof value === 'object' &&
        value !== null &&
        'code' in value &&
        'trace_id' in value &&
        typeof (value as components['schemas']['Problem']).code === 'string' &&
        typeof (value as components['schemas']['Problem']).trace_id === 'string'
    )
}

async function toApiError(res: Response): Promise<ApiError> {
    const body: unknown = await res
        .text()
        .then((text) => (text === '' ? undefined : JSON.parse(text)))
        .catch(() => undefined)
    if (isProblem(body)) {
        return new ApiError({
            status: body.status,
            title: body.title,
            code: body.code,
            type: body.type,
            detail: body.detail,
            trace_id: body.trace_id,
        })
    }
    return new ApiError({ status: res.status, title: res.statusText || `HTTP ${res.status}` })
}

async function performRequest(
    method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
    path: string,
    opts: RequestOptions & { idempotencyKey?: string },
    body?: unknown,
): Promise<unknown> {
    const headers: Record<string, string> = {
        Accept: 'application/json, application/problem+json',
    }
    if (opts.token) headers.Authorization = `Bearer ${opts.token}`
    if (opts.idempotencyKey) headers['Idempotency-Key'] = opts.idempotencyKey
    if (body !== undefined) headers['Content-Type'] = 'application/json'

    const res = await fetch(buildUrl(path, opts), {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
    })

    if (res.status === 401) opts.onUnauthorized?.()

    if (!res.ok) throw await toApiError(res)
    if (res.status === 204) return undefined
    const contentType = res.headers.get('content-type') ?? ''
    if (!contentType.includes('json')) return undefined
    const text = await res.text()
    return text === '' ? undefined : JSON.parse(text)
}

export async function apiGet<P extends PathOf<'get'>>(
    path: P,
    opts: RequestOptions = {},
): Promise<SuccessBody<Operation<P, 'get'>>> {
    return performRequest('GET', path, opts) as Promise<SuccessBody<Operation<P, 'get'>>>
}

export async function apiPost<P extends PathOf<'post'>>(
    path: P,
    body: RequestBody<Operation<P, 'post'>>,
    opts: IdempotencyOptions<Operation<P, 'post'>> & RequestOptions,
): Promise<SuccessBody<Operation<P, 'post'>>> {
    return performRequest('POST', path, opts, body) as Promise<SuccessBody<Operation<P, 'post'>>>
}

export async function apiPatch<P extends PathOf<'patch'>>(
    path: P,
    body: RequestBody<Operation<P, 'patch'>>,
    opts: IdempotencyOptions<Operation<P, 'patch'>> & RequestOptions,
): Promise<SuccessBody<Operation<P, 'patch'>>> {
    return performRequest('PATCH', path, opts, body) as Promise<SuccessBody<Operation<P, 'patch'>>>
}

export async function apiDelete<P extends PathOf<'delete'>>(
    path: P,
    opts: IdempotencyOptions<Operation<P, 'delete'>> & RequestOptions =
        {} as IdempotencyOptions<Operation<P, 'delete'>> & RequestOptions,
): Promise<SuccessBody<Operation<P, 'delete'>>> {
    return performRequest('DELETE', path, opts) as Promise<SuccessBody<Operation<P, 'delete'>>>
}
