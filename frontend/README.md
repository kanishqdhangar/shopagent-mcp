# ShopAgent frontend

Responsive React and TypeScript interface for the ShopAgent buyer assistant and seller catalogue.

## Prerequisites

- Node.js compatible with the installed Vite 8 toolchain
- npm
- Buyer agent available at `http://localhost:8001`
- Seller service available at `http://localhost:8000`

## Install and run

```powershell
cd frontend
npm install
npm run dev
```

Vite serves the interface at `http://localhost:5173`.

## Backend proxy configuration

The development server proxies `/api/*` to `http://localhost:8001/*` and `/seller-api/*` to `http://localhost:8000/*`, removing the frontend prefix. These targets are configured in `vite.config.ts`. No frontend environment variables or credentials are needed.

From the repository root, start the backend services with `docker compose up --build -d`. Confirm service startup with `docker compose ps`. The top bar checks `GET /health` on the buyer agent.

## Features

- Assistant chat with Markdown responses, per-conversation sessions, locally stored conversation metadata and messages, and explicit alternative approval/rejection.
- Razorpay Checkout receives the public key ID, Razorpay order ID, amount, and currency from the backend. The browser callback is never treated as payment proof; the frontend checks the seller order status until it confirms a result.
- Discover page with seller catalogue retrieval (`GET /products?limit=50`) and semantic search (`POST /products/search`).
- My Orders page reports that order history is not exposed by the current backend. Per-chat order status is shown when returned by the buyer agent.
- Responsive navigation, loading/error/empty states, and INR product pricing.

Conversation messages are stored in this browser's local storage. They are not backend-persisted. Order history is not exposed by the current services; an order status is readable by its ShopAgent order ID.

## Build

```powershell
npm run build
npm run preview
```

The Vite development server and Docker backend can run concurrently. From the repository root, stop the backend with `docker compose down` when finished.
