import createFetchClient from 'openapi-fetch'
import createQueryClient from 'openapi-react-query'
import type { paths } from './openapi.gen.ts'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export const apiFetch = createFetchClient<paths>({
  baseUrl: API_BASE_URL
})

export const $api = createQueryClient(apiFetch)
