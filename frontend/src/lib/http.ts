import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

const DEFAULT_TIMEOUT_MS = 15_000

export class ApiError extends Error {
  readonly status: number | null
  readonly isNetworkError: boolean

  constructor(message: string, status: number | null, isNetworkError = false) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.isNetworkError = isNetworkError
  }
}

export interface HttpOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  timeoutMs?: number
}

function requestUrl(path: string): string {
  return `${env.apiBaseUrl}/${path.replace(/^\/+/, '')}`
}

async function responseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined

  const contentType = response.headers.get('content-type')
  if (contentType?.includes('application/json')) return response.json()

  return response.text()
}

function errorMessage(body: unknown, response: Response): string {
  if (
    typeof body === 'object' &&
    body !== null &&
    'detail' in body &&
    typeof body.detail === 'string'
  ) {
    return body.detail
  }

  if (typeof body === 'string' && body !== '') return body
  return `${response.status} ${response.statusText}`
}

export async function request<T>(
  path: string,
  options: HttpOptions = {},
): Promise<T> {
  const { body, headers: initialHeaders, timeoutMs, ...init } = options
  const headers = new Headers(initialHeaders)
  const { data, error } = await supabase.auth.getSession()

  if (error) throw new ApiError(error.message, null)
  if (data.session) {
    headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }

  let requestBody: BodyInit | undefined
  if (body instanceof FormData || typeof body === 'string') {
    requestBody = body
  } else if (body !== undefined) {
    headers.set('Content-Type', 'application/json')
    requestBody = JSON.stringify(body)
  }

  const timeoutSignal = AbortSignal.timeout(timeoutMs ?? DEFAULT_TIMEOUT_MS)
  const signal = init.signal
    ? AbortSignal.any([init.signal, timeoutSignal])
    : timeoutSignal

  let response: Response
  try {
    response = await fetch(requestUrl(path), {
      ...init,
      body: requestBody,
      headers,
      signal,
    })
  } catch (error) {
    const message =
      error instanceof DOMException && error.name === 'TimeoutError'
        ? 'Request timed out'
        : 'Unable to reach the API'
    throw new ApiError(message, null, true)
  }

  const parsedBody = await responseBody(response)
  if (!response.ok) {
    throw new ApiError(errorMessage(parsedBody, response), response.status)
  }

  return parsedBody as T
}
