import { useEffect, useMemo, useRef, useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ArrowRight, Bot, Compass, Menu, MessageSquare, Package, Plus, Search, Send, ShieldCheck, ShoppingBag, Sparkles, ThumbsDown, ThumbsUp, X } from 'lucide-react'
import { checkHealth, getOrderStatus, getProducts, searchProducts, sendChat, sendConfirmation } from './services/api'
import type { AgentResponse, ChatMessage, Conversation, PaymentDetails, Product } from './types/api'
import './App.css'

const prompts = ['Find wireless headphones under ₹3,000', 'Recommend a laptop for programming', 'Find the best value products under ₹5,000', 'Compare running shoes']

declare global {
  interface Window { Razorpay?: new (options: RazorpayOptions) => { open: () => void; on: (event: string, callback: (error: unknown) => void) => void } }
}
type RazorpayOptions = {
  key: string; amount: number; currency: string; name: string; order_id: string; description: string
  handler: (result: { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string }) => void
  modal: { ondismiss: () => void }
}
const newConversation = (): Conversation => ({ id: crypto.randomUUID(), title: 'New conversation', updatedAt: Date.now(), messages: [] })
const readConversations = (): Conversation[] => {
  try { const saved = localStorage.getItem('shopagent.conversations'); return saved ? JSON.parse(saved) as Conversation[] : [] } catch { return [] }
}
const price = (value?: string | number) => {
  if (value === undefined || value === null || value === '') return 'Price unavailable'
  const amount = Number(value)
  return Number.isFinite(amount) ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(amount) : 'Price unavailable'
}
function productFrom(result: AgentResponse): Omit<ChatMessage, 'id' | 'role'> {
  return { content: result.response, products: result.products ?? [], confirmation: result.confirmation_required ? result.pending_confirmation : null, orderStatus: result.order_status, orderId: result.order_id, failureReason: result.failure_reason, payment: result.payment, paymentRequired: result.payment_required, negotiation: result.negotiation }
}

function PaymentSummary({ payment, state, onStart }: { payment: PaymentDetails; state: string; onStart: () => void }) {
  return <section className="payment-summary" aria-label="Payment summary"><div className="payment-heading"><div className="approval-icon"><ShoppingBag size={17}/></div><div><strong>Complete your order</strong><span>Payment is securely processed by Razorpay.</span></div><span className={`payment-badge ${state === 'paid' ? 'paid' : state === 'failed' ? 'failed' : ''}`}>{state === 'paid' ? 'Paid' : state === 'failed' ? 'Payment failed' : state === 'verifying' ? 'Verifying payment' : 'Payment required'}</span></div><div className="payment-items">{payment.items.map((item, i) => <div className="payment-line" key={`${item.product_id}-${i}`}><span>{item.name} <small>× {item.quantity}</small></span><b>{price(item.line_total)}</b></div>)}</div><div className="payment-total"><span>Total · {payment.currency}</span><strong>{price(payment.amount)}</strong></div>{state === 'verifying' ? <div className="payment-feedback"><span className="spinner"/>Waiting for the seller to verify payment. This can take a few moments.</div> : state === 'paid' ? <div className="payment-feedback success"><ShieldCheck size={15}/> Payment confirmed by the seller.</div> : state === 'failed' ? <div className="payment-feedback failed">The seller reported that this payment failed. Contact support before trying again.</div> : <button className="button primary pay-button" onClick={onStart} disabled={state === 'opening'}>{state === 'opening' ? 'Opening secure checkout…' : 'Pay securely with Razorpay'}</button>}<small className="payment-disclaimer">Your payment is not complete until the seller confirms it.</small></section>
}

function ProductCard({ product, recommended = false }: { product: Product; recommended?: boolean }) {
  return <article className="product-card">
    <div className="product-meta"><span>{product.category || product.subtype || 'PRODUCT'}</span>{product.stock_qty !== undefined && <span className={product.stock_qty > 0 ? 'stock in-stock' : 'stock out-stock'}>{product.stock_qty > 0 ? `${product.stock_qty} in stock` : 'Out of stock'}</span>}</div>
    <h3>{product.name || 'Unnamed product'}</h3>
    {product.description && <p>{product.description}</p>}
    <div className="product-footer"><strong>{price(product.price)}</strong>{recommended && <span className="recommendation"><Sparkles size={13} /> Agent pick</span>}</div>
  </article>
}

function Assistant({ conversation, updateConversation, busy, setBusy }: { conversation: Conversation; updateConversation: (fn: (c: Conversation) => Conversation) => void; busy: boolean; setBusy: (value: boolean) => void }) {
  const [draft, setDraft] = useState('')
  const [confirming, setConfirming] = useState<string | null>(null)
  const [paymentStates, setPaymentStates] = useState<Record<string, string>>({})
  const [counterFor, setCounterFor] = useState<string | null>(null)
  const [counterValue, setCounterValue] = useState('')
  const paymentAttempts = useRef(new Set<string>())
  const paymentPolls = useRef(new Map<string, AbortController>())
  const checkedPaymentOrders = useRef(new Set<string>())
  useEffect(() => () => {
    for (const controller of paymentPolls.current.values()) controller.abort()
    paymentPolls.current.clear()
  }, [])
  const submit = async (text = draft) => {
    const message = text.trim()
    if (!message || busy) return
    setDraft(''); setBusy(true)
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: message }
    updateConversation((c) => ({ ...c, title: c.messages.length ? c.title : message.slice(0, 34), updatedAt: Date.now(), messages: [...c.messages, userMessage] }))
    try {
      const result = await sendChat(message, conversation.id)
      updateConversation((c) => ({ ...c, updatedAt: Date.now(), messages: [...c.messages, { id: crypto.randomUUID(), role: 'assistant', ...productFrom(result) }] }))
    } catch (error) {
      updateConversation((c) => ({ ...c, messages: [...c.messages, { id: crypto.randomUUID(), role: 'assistant', content: error instanceof Error ? error.message : 'Unable to reach the shopping assistant.' }] }))
    } finally { setBusy(false) }
  }
  const confirm = async (approved: boolean, messageId: string) => {
    if (confirming) return
    setConfirming(messageId)
    try {
      const result = await sendConfirmation(conversation.id, approved)
      updateConversation((c) => ({ ...c, messages: [...c.messages.map((m) => m.id === messageId ? { ...m, confirmation: null } : m), { id: crypto.randomUUID(), role: 'assistant', ...productFrom(result) }] }))
    } catch (error) {
      updateConversation((c) => ({ ...c, messages: [...c.messages, { id: crypto.randomUUID(), role: 'assistant', content: error instanceof Error ? error.message : 'Could not process your decision.' }] }))
    } finally { setConfirming(null) }
  }
  const pollOrder = async (orderId: string) => {
    if (paymentPolls.current.has(orderId)) return
    const controller = new AbortController()
    paymentPolls.current.set(orderId, controller)
    setPaymentStates((s) => ({ ...s, [orderId]: 'verifying' }))
    let attempt = 0
    while (!controller.signal.aborted) {
      try {
        const status = await getOrderStatus(orderId, controller.signal)
        if (status.payment_status === 'paid' || status.status === 'paid') { setPaymentStates((s) => ({ ...s, [orderId]: 'paid' })); return }
        if (status.payment_status === 'failed' || status.status === 'payment_failed') { setPaymentStates((s) => ({ ...s, [orderId]: 'failed' })); return }
      } catch { if (controller.signal.aborted) break /* Transient errors do not mean payment failed. */ }
      const delay = attempt < 40 ? 3000 : 15000
      await new Promise<void>((resolve) => {
        const onAbort = () => { window.clearTimeout(timer); resolve() }
        const timer = window.setTimeout(() => { controller.signal.removeEventListener('abort', onAbort); resolve() }, delay)
        controller.signal.addEventListener('abort', onAbort, { once: true })
      })
      attempt++
    }
    paymentPolls.current.delete(orderId)
  }
  useEffect(() => {
    for (const message of conversation.messages) {
      const payment = message.payment
      if (!message.paymentRequired || !payment || checkedPaymentOrders.current.has(payment.order_id)) continue
      checkedPaymentOrders.current.add(payment.order_id)
      void getOrderStatus(payment.order_id).then((status) => {
        if (status.payment_status === 'paid' || status.status === 'paid') setPaymentStates((s) => ({ ...s, [payment.order_id]: 'paid' }))
        else if (status.payment_status === 'failed' || status.status === 'payment_failed') setPaymentStates((s) => ({ ...s, [payment.order_id]: 'failed' }))
      }).catch(() => { checkedPaymentOrders.current.delete(payment.order_id) })
    }
  }, [conversation.messages])
  const startPayment = async (payment: PaymentDetails) => {
    const current = paymentStates[payment.order_id]
    if (paymentAttempts.current.has(payment.order_id) || current === 'opening' || current === 'verifying' || current === 'paid') return
    paymentAttempts.current.add(payment.order_id)
    setPaymentStates((s) => ({ ...s, [payment.order_id]: 'opening' }))
    try {
      const serverStatus = await getOrderStatus(payment.order_id)
      if (serverStatus.payment_status === 'paid' || serverStatus.status === 'paid') { setPaymentStates((s) => ({ ...s, [payment.order_id]: 'paid' })); return }
      if (serverStatus.payment_status === 'failed' || serverStatus.status === 'payment_failed') { setPaymentStates((s) => ({ ...s, [payment.order_id]: 'failed' })); return }
      if (!window.Razorpay) {
        await new Promise<void>((resolve, reject) => {
          const existing = document.querySelector<HTMLScriptElement>('script[data-razorpay-checkout]')
          if (existing) { existing.addEventListener('load', () => resolve(), { once: true }); existing.addEventListener('error', () => reject(new Error('Razorpay Checkout could not be loaded.')), { once: true }); return }
          const script = document.createElement('script'); script.src = 'https://checkout.razorpay.com/v1/checkout.js'; script.async = true; script.dataset.razorpayCheckout = 'true'; script.onload = () => resolve(); script.onerror = () => reject(new Error('Razorpay Checkout could not be loaded.')); document.body.appendChild(script)
        })
      }
      if (!window.Razorpay) throw new Error('Razorpay Checkout is unavailable.')
      let verificationStarted = false
      const checkout = new window.Razorpay({ key: payment.key_id, amount: payment.amount_paise, currency: payment.currency, name: 'ShopAgent', order_id: payment.razorpay_order_id, description: 'ShopAgent order', handler: () => { verificationStarted = true; void pollOrder(payment.order_id) }, modal: { ondismiss: () => { if (!verificationStarted) { paymentAttempts.current.delete(payment.order_id); setPaymentStates((s) => ({ ...s, [payment.order_id]: 'idle' })) } } } })
      checkout.on('payment.failed', () => { verificationStarted = true; void pollOrder(payment.order_id) })
      checkout.open()
      setPaymentStates((s) => ({ ...s, [payment.order_id]: 'opening' }))
    } catch (error) {
      paymentAttempts.current.delete(payment.order_id)
      setPaymentStates((s) => ({ ...s, [payment.order_id]: 'idle' }))
      updateConversation((c) => ({ ...c, messages: [...c.messages, { id: crypto.randomUUID(), role: 'assistant', content: error instanceof Error ? error.message : 'Could not open payment checkout.' }] }))
    }
  }
  return <div className="workspace chat-workspace">
    <div className="page-title"><div className="title-icon"><Sparkles size={19}/></div><div><h1>Shopping assistant</h1><p>Discover products and make confident choices.</p></div><span className="session-pill"><ShieldCheck size={14}/> Private session</span></div>
    <div className="conversation-scroll">
      {!conversation.messages.length ? <div className="welcome"><div className="welcome-orb"><Sparkles size={26}/></div><span className="eyebrow">YOUR PERSONAL SHOPPING AGENT</span><h2>What are we shopping for today?</h2><p>Tell me what you need, your budget, or what matters most. I’ll search and compare based on your request.</p><div className="prompt-grid">{prompts.map((prompt, i) => <button key={prompt} onClick={() => void submit(prompt)} disabled={busy}><span className="prompt-index">0{i + 1}</span><span>{prompt}</span><ArrowRight size={16}/></button>)}</div></div> : <div className="messages">{conversation.messages.map((message) => <div className={`message ${message.role}`} key={message.id}>{message.role === 'assistant' && <div className="bot-avatar"><Bot size={17}/></div>}<div className="message-body"><div className="message-label">{message.role === 'assistant' ? 'SHOPAGENT' : 'YOU'}{message.role === 'assistant' && <span>ASSISTANT</span>}</div><div className={`message-copy ${message.role === 'assistant' ? 'markdown-content' : ''}`}>{message.role === 'assistant' ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown> : message.content}</div>
        {!!message.products?.length && <div className="product-grid">{message.products.map((product, i) => <ProductCard key={product.id || `${product.name}-${i}`} product={product} recommended={message.products?.length === 1}/>)}</div>}
        {message.negotiation && <section className="negotiation-card">
          <div className="negotiation-heading"><div><span className="eyebrow">NEGOTIATION</span><h3>{message.negotiation.product_name || 'Seller offer'}</h3></div><span className={`negotiation-status ${message.negotiation.status || ''}`}>{(message.negotiation.status || 'offer').replaceAll('_', ' ')}</span></div>
          {message.negotiation.original_price !== undefined && <div className="negotiation-prices"><div><span>Original price</span><b>{price(message.negotiation.original_price)}</b></div><div><span>Discount</span><b>{Number(message.negotiation.discount_percent || 0).toFixed(2)}%</b></div><div><span>You save</span><b>{price(Number(message.negotiation.original_price) - Number(message.negotiation.discounted_price))}</b></div><div className="negotiation-final"><span>Offer price</span><b>{price(message.negotiation.discounted_price)}</b></div></div>}
          {!!message.negotiation.history?.length && <div className="negotiation-history"><span>Offer history</span>{message.negotiation.history.slice(-4).map((item, i) => <small key={`${item.status}-${i}`}>{item.status.replaceAll('_', ' ')}{item.discount_percent !== undefined ? ` · ${item.discount_percent}%` : ''}{item.price !== undefined ? ` · ${price(item.price)}` : ''}</small>)}</div>}
          {(message.negotiation.status === 'pending' || message.negotiation.status === 'maximum_reached') && <div className="negotiation-actions"><button className="button primary" disabled={busy} onClick={() => void submit('I accept the offer')}>Accept offer</button><button className="button subtle" disabled={busy} onClick={() => { setCounterFor(counterFor === message.id ? null : message.id); setCounterValue('') }}>Counteroffer</button><button className="button subtle" disabled={busy} onClick={() => void submit("I reject this offer")}>Reject</button></div>}
          {counterFor === message.id && <form className="counteroffer" onSubmit={(e) => { e.preventDefault(); const value = counterValue.trim(); if (!value) return; const messageText = value.includes('%') ? `Can you give me ${value} off?` : `I can buy it for ₹${value}`; setCounterFor(null); setCounterValue(''); void submit(messageText) }}><input aria-label="Counteroffer percentage or target price" value={counterValue} onChange={(e) => setCounterValue(e.target.value)} placeholder="e.g. 10% or 2000"/><button className="button primary" type="submit" disabled={busy || !counterValue.trim()}>Send counteroffer</button></form>}
        </section>}
        {message.paymentRequired && message.payment && <PaymentSummary payment={message.payment} state={paymentStates[message.payment.order_id] || 'idle'} onStart={() => void startPayment(message.payment!)}/>}
        {message.confirmation && <div className="approval"><div className="approval-heading"><div className="approval-icon"><ShieldCheck size={18}/></div><div><strong>Approval needed</strong><p>The agent found an alternative. Review it before deciding; no order proceeds without your approval.</p></div></div><div className="approval-product"><ShoppingBag size={18}/><div><strong>{message.confirmation.name || 'Suggested alternative'}</strong><span>{price(message.confirmation.price)}</span></div></div><div className="approval-actions"><button className="button subtle" onClick={() => void confirm(false, message.id)} disabled={!!confirming}><ThumbsDown size={15}/> Reject</button><button className="button primary" onClick={() => void confirm(true, message.id)} disabled={!!confirming}>{confirming === message.id ? 'Processing…' : <><ThumbsUp size={15}/> Approve alternative</>}</button></div></div>}
        {(() => { const status = message.payment?.order_id && paymentStates[message.payment.order_id] === 'paid' ? 'paid' : message.payment?.order_id && paymentStates[message.payment.order_id] === 'failed' ? 'failed' : message.orderStatus; return status && status !== 'not_started' ? <div className="order-note"><Package size={15}/><span>Order status: <b>{status.replaceAll('_', ' ')}</b>{message.orderId ? ` · ${message.orderId}` : ''}</span></div> : null })()}{message.failureReason && <div className="error-note"><X size={14}/>{message.failureReason}</div>}
      </div></div>)}</div>}
      {busy && <div className="thinking"><span/><span/><span/> Searching the catalogue…</div>}
    </div>
    <div className="composer-wrap"><form className="composer" onSubmit={(e) => { e.preventDefault(); void submit() }}><textarea rows={1} value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit() } }} placeholder="Describe what you’re looking for…" disabled={busy}/><div className="composer-bottom"><span><Sparkles size={14}/> AI-powered shopping</span><button type="submit" aria-label="Send message" disabled={!draft.trim() || busy}><Send size={17}/></button></div></form><small>Review product details before purchasing. The agent will ask before proceeding with alternatives.</small></div>
  </div>
}

function Discover() {
  const [items, setItems] = useState<Product[]>([]); const [query, setQuery] = useState(''); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [searched, setSearched] = useState(false)
  const load = async () => { setLoading(true); setError(''); try { setItems(await getProducts()); setSearched(false) } catch (e) { setError(e instanceof Error ? e.message : 'Catalogue unavailable') } finally { setLoading(false) } }
  const retry = async () => { if (!query.trim()) { await load(); return } setLoading(true); setError(''); try { setItems(await searchProducts(query.trim())) } catch (e) { setError(e instanceof Error ? e.message : 'Search unavailable') } finally { setLoading(false) } }
  useEffect(() => {
    let mounted = true
    void getProducts().then((products) => { if (mounted) setItems(products) }).catch((e: unknown) => { if (mounted) setError(e instanceof Error ? e.message : 'Catalogue unavailable') }).finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [])
  const search = async (e: React.FormEvent) => { e.preventDefault(); if (!query.trim()) { void load(); return } setLoading(true); setError(''); setSearched(true); try { setItems(await searchProducts(query.trim())) } catch (e) { setError(e instanceof Error ? e.message : 'Search unavailable') } finally { setLoading(false) } }
  return <div className="workspace page-workspace"><div className="page-title"><div className="title-icon"><Compass size={19}/></div><div><h1>Discover products</h1><p>Explore the seller catalogue or search by what you need.</p></div></div><form className="search-bar" onSubmit={(e) => void search(e)}><Search size={18}/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search products, categories, or needs…"/><button className="button primary" type="submit" disabled={loading}>Search</button></form><div className="section-heading"><h2>{searched ? `Search results` : 'Catalogue'}</h2><span>{loading ? 'Loading…' : `${items.length} ${items.length === 1 ? 'product' : 'products'}`}</span></div>{loading ? <div className="empty-state"><span className="spinner"/>Loading products…</div> : error ? <div className="empty-state error-state"><strong>Couldn’t load products</strong><p>{error}</p><button className="button subtle" onClick={() => void retry()}>Try again</button></div> : !items.length ? <div className="empty-state"><div className="empty-icon"><Search size={20}/></div><strong>{searched ? 'No matching products' : 'Catalogue is empty'}</strong><p>{searched ? 'Try a broader search or a different phrase.' : 'Products will appear here when they are available from the seller service.'}</p></div> : <div className="catalog-grid">{items.map((product, i) => <ProductCard key={product.id || `${product.name}-${i}`} product={product}/>)}</div>}</div>
}

function Orders() { return <div className="workspace page-workspace"><div className="page-title"><div className="title-icon"><Package size={19}/></div><div><h1>My orders</h1><p>Order updates from your shopping sessions.</p></div></div><div className="orders-empty"><div className="empty-icon"><Package size={23}/></div><span className="eyebrow">ORDER HISTORY</span><h2>Order history isn’t available yet</h2><p>The current backend doesn’t expose an order history endpoint. Order status returned during this conversation appears in the assistant chat.</p><NavLink className="button primary" to="/assistant">Return to assistant <ArrowRight size={15}/></NavLink></div></div> }

function Shell() {
  const [conversations, setConversations] = useState<Conversation[]>(readConversations)
  const [activeId, setActiveId] = useState(() => readConversations()[0]?.id ?? '')
  const [online, setOnline] = useState(false); const [mobileOpen, setMobileOpen] = useState(false); const [busy, setBusy] = useState(false)
  const location = useLocation(); const navigate = useNavigate()
  useEffect(() => { localStorage.setItem('shopagent.conversations', JSON.stringify(conversations)) }, [conversations])
  useEffect(() => { void checkHealth().then(() => setOnline(true)).catch(() => setOnline(false)); const id = window.setInterval(() => void checkHealth().then(() => setOnline(true)).catch(() => setOnline(false)), 20000); return () => clearInterval(id) }, [])
  const active = useMemo(() => conversations.find((c) => c.id === activeId), [conversations, activeId])
  const updateConversation = (fn: (c: Conversation) => Conversation) => setConversations((all) => all.map((c) => c.id === activeId ? fn(c) : c))
  const startNew = () => { const c = newConversation(); setConversations((all) => [c, ...all]); setActiveId(c.id); navigate('/assistant'); setMobileOpen(false) }
  const choose = (id: string) => { setActiveId(id); navigate('/assistant'); setMobileOpen(false) }
  const activeTitle = location.pathname.includes('discover') ? 'Discover' : location.pathname.includes('orders') ? 'My orders' : 'Assistant'
  return <div className="app-shell"><button className="mobile-menu" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Toggle navigation"><Menu size={20}/></button>{mobileOpen && <button className="mobile-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation"/>}<aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}><div className="brand"><div className="brand-mark"><Sparkles size={18}/></div><span>shopagent<span className="brand-dot">.</span></span></div><button className="new-chat" onClick={startNew}><Plus size={16}/> New conversation</button><div className="nav-label">WORKSPACE</div><nav className="nav-list"><NavLink to="/assistant" onClick={() => setMobileOpen(false)} className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}><MessageSquare size={17}/>Assistant</NavLink><NavLink to="/discover" onClick={() => setMobileOpen(false)} className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}><Compass size={17}/>Discover</NavLink><NavLink to="/orders" onClick={() => setMobileOpen(false)} className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}><Package size={17}/>My orders</NavLink></nav><div className="nav-label recent-label">RECENT CONVERSATIONS</div><div className="recent-list">{conversations.filter((c) => c.messages.length).slice(0, 8).map((c) => <button className={`recent-item ${c.id === activeId ? 'selected' : ''}`} key={c.id} onClick={() => choose(c.id)}><MessageSquare size={14}/><span>{c.title}</span></button>)}{!conversations.some(c => c.messages.length) && <div className="recent-placeholder">Your conversations will show here.</div>}</div><div className="sidebar-bottom"><div className="trust-card"><ShieldCheck size={17}/><div><strong>Shop with confidence</strong><p>You stay in control of every purchase.</p></div></div><div className="profile"><span className="profile-avatar">S</span><div><b>Shopper</b><small>Personal workspace</small></div></div></div></aside><main className="main-panel"><header className="topbar"><div><span>Workspace</span><i>/</i><b>{activeTitle}</b></div><div className="topbar-right"><span className={`connection ${online ? 'is-online' : ''}`}><i/>{online ? 'Agent connected' : 'Agent offline'}</span><span className="top-avatar">S</span></div></header><Routes><Route path="/" element={<AssistantRoute {...{active, activeId, setConversations, setActiveId, updateConversation, busy, setBusy, startNew}}/>}/><Route path="/assistant" element={<AssistantRoute {...{active, activeId, setConversations, setActiveId, updateConversation, busy, setBusy, startNew}}/>}/><Route path="/discover" element={<Discover/>}/><Route path="/orders" element={<Orders/>}/><Route path="*" element={<AssistantRoute {...{active, activeId, setConversations, setActiveId, updateConversation, busy, setBusy, startNew}}/>}/></Routes></main></div>
}

function AssistantRoute({ active, activeId, setConversations, setActiveId, updateConversation, busy, setBusy, startNew }: { active?: Conversation; activeId: string; setConversations: React.Dispatch<React.SetStateAction<Conversation[]>>; setActiveId: (id: string) => void; updateConversation: (fn: (c: Conversation) => Conversation) => void; busy: boolean; setBusy: (v: boolean) => void; startNew: () => void }) {
  useEffect(() => { if (!activeId || !active) { const c = newConversation(); setConversations((all) => [c, ...all]); setActiveId(c.id) } }, [activeId, active, setActiveId, setConversations])
  if (!active) return <div className="empty-state"><button className="button primary" onClick={startNew}>Start a conversation</button></div>
  return <Assistant key={active.id} conversation={active} updateConversation={updateConversation} busy={busy} setBusy={setBusy}/>
}

export default function App() { return <BrowserRouter><Shell/></BrowserRouter> }
