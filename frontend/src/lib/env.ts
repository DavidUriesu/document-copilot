type EnvironmentKey =
  | 'VITE_API_BASE_URL'
  | 'VITE_SUPABASE_URL'
  | 'VITE_SUPABASE_ANON_KEY'

function requiredValue(key: EnvironmentKey): string {
  const value = import.meta.env[key]

  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`Missing required environment variable: ${key}`)
  }

  return value.trim()
}

function requiredUrl(key: EnvironmentKey): string {
  const value = requiredValue(key)
  let url: URL

  try {
    url = new URL(value)
  } catch {
    throw new Error(`${key} must be a valid URL`)
  }

  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error(`${key} must use http or https`)
  }

  return value.replace(/\/+$/, '')
}

export const env = Object.freeze({
  apiBaseUrl: requiredUrl('VITE_API_BASE_URL'),
  supabaseUrl: requiredUrl('VITE_SUPABASE_URL'),
  supabaseAnonKey: requiredValue('VITE_SUPABASE_ANON_KEY'),
})
