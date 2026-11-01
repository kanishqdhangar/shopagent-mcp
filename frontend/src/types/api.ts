export type Product = {
  id?: string
  name?: string
  category?: string
  subtype?: string | null
  price?: number | string
  description?: string | null
  stock_qty?: number
  brand?: string
  size?: string | null
  spec_json?: Record<string, unknown> | null
}

export type AgentResponse = {
  response: string
  session_id: string
  intent_type?: string
  products?: Product[]
  confirmation_required?: boolean
  pending_confirmation?: Product | null
  order_status?: string
  order_id?: string | null
  failure_reason?: string | null
  payment_required?: boolean
  payment?: PaymentDetails | null
  payment_status?: string | null
  negotiation?: NegotiationOffer | null
}

export type NegotiationOffer = {
  product_id?: string
  product_name?: string
  original_price?: number
  discount_percent?: number
  discounted_price?: number
  status?: string
  maximum_discount_percent?: number
  rejection_reason?: string | null
  history?: { status: string; discount_percent?: number; price?: number; reason?: string }[]
}

export type PaymentDetails = {
  order_id: string
  razorpay_order_id: string
  amount: number
  amount_paise: number
  currency: string
  key_id: string
  items: { product_id: string; name: string; quantity: number; unit_price: number; line_total: number }[]
}

export type OrderStatus = { order_id: string; status: string; payment_status: string; razorpay_payment_id?: string | null; total_amount: number; currency: string; cart: PaymentDetails['items'] }

export type ChatMessage = {
  id: string
  role: 'assistant' | 'user'
  content: string
  products?: Product[]
  confirmation?: Product | null
  orderStatus?: string
  orderId?: string | null
  failureReason?: string | null
  payment?: PaymentDetails | null
  paymentRequired?: boolean
  negotiation?: NegotiationOffer | null
}

export type Conversation = { id: string; title: string; updatedAt: number; messages: ChatMessage[] }
