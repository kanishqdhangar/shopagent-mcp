import type { AgentResponse, OrderStatus, Product } from '../types/api'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const data: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const body = data as { detail?: unknown; message?: unknown } | null
    const detail = body?.detail ?? body?.message
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status})`)
  }
  return data as T
}

export const checkHealth = () => request<{ status: string }>('/api/health')
export const sendChat = (message: string, sessionId: string) => request<AgentResponse>('/api/chat', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, session_id: sessionId }),
})
export const sendConfirmation = (sessionId: string, approved: boolean) => request<AgentResponse>('/api/chat/confirmation', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, approved }),
})
export const getProducts = () => request<Product[]>('/seller-api/products?limit=50')
export const searchProducts = async (query: string) => {
  const data = await request<{ results: { product: Product }[] }>('/seller-api/products/search', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query, limit: 10 }),
  })
  return data.results.map((item) => item.product)
}
export const getOrderStatus = (orderId: string, signal?: AbortSignal) => request<OrderStatus>(`/seller-api/orders/${encodeURIComponent(orderId)}`, { signal })
