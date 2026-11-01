# ShopAgent

**An agentic commerce system that helps users discover, compare, and
purchase products through a conversational shopping workflow.**

ShopAgent is a multi-service application built around an AI-powered
buyer agent, seller-side product and commerce tools, PostgreSQL with
`pgvector`, Redis, and asynchronous background processing.

The project focuses not only on product discovery, but also on safe
purchasing: explicit user approval for alternative products,
deterministic budget checks, payment-status confirmation, persistent
workflow state, and reliable audit-event delivery.

> **Project status:** Core shopping and checkout workflows,
> alternative-product approval, payment confirmation, Redis-backed
> LangGraph checkpointing, and transactional audit outbox processing
> have been implemented and tested. Some integrations and user-facing
> components may still be under development. This repository should be
> treated as an actively developed project, not represented as a fully
> production-hardened commerce platform.

------------------------------------------------------------------------

## Table of contents

-   [Highlights](#highlights)
-   [Architecture](#architecture)
-   [Shopping workflow](#shopping-workflow)
-   [Technology stack](#technology-stack)
-   [Reliability and safety](#reliability-and-safety)
-   [Repository structure](#repository-structure)
-   [Getting started](#getting-started)
-   [Running the tests](#running-the-tests)
-   [Example scenarios](#example-scenarios)
-   [Configuration and secrets](#configuration-and-secrets)
-   [Current scope and limitations](#current-scope-and-limitations)

------------------------------------------------------------------------

## Highlights

-   **Conversational shopping agent:** Interprets shopping requests and
    coordinates product retrieval, comparison, and purchase workflows.
-   **Agent orchestration:** Uses LangGraph to model the buyer-agent
    workflow and its conditional transitions.
-   **MCP-based commerce tools:** Separates the buyer agent from
    seller-side capabilities through tool interfaces.
-   **Semantic product retrieval:** Uses PostgreSQL and `pgvector` for
    embedding-based product retrieval.
-   **Deterministic budget guardrail:** Prevents a purchase when the
    selected product exceeds the user's explicit budget.
-   **Human approval for alternatives:** If the selected product is out
    of stock, the agent can offer an eligible alternative and wait for
    explicit approval before ordering it.
-   **Payment confirmation:** Handles payment-status polling and pending
    outcomes rather than assuming that order creation means payment
    completion.
-   **Persistent workflow state:** Uses Redis-backed LangGraph
    checkpoints to support interrupt-and-resume flows.
-   **Transactional audit outbox:** Persists audit events for
    asynchronous delivery, with retries and dead-letter handling.
-   **Background processing:** Uses Redis-backed workers for
    asynchronous tasks.

------------------------------------------------------------------------

## Architecture

ShopAgent is organized into independently running services and
infrastructure components.

``` mermaid
flowchart TD
    User[User / Client] --> Buyer[Buyer Agent]
    Buyer --> Graph[LangGraph Workflow]
    Graph --> MCP[MCP Client / Tools]
    MCP --> Seller[Seller Service]
    Seller --> DB[(PostgreSQL + pgvector)]
    Graph --> Redis[(Redis)]
    Graph --> Outbox[(Audit Outbox)]
    Outbox --> Worker[Outbox Worker]
    Worker --> Audit[(Audit Log)]
    Seller --> Payment[Payment Provider]
```

### Main components

  -----------------------------------------------------------------------
  Component                           Responsibility
  ----------------------------------- -----------------------------------
  Buyer agent                         Interprets the user's shopping goal
                                      and coordinates the shopping
                                      workflow.

  LangGraph workflow                  Controls workflow state, node
                                      execution, conditional routing, and
                                      approval interrupts.

  MCP client and tools                Provide a structured interface
                                      between the buyer agent and
                                      commerce capabilities.

  Seller service                      Exposes product, inventory, and
                                      order-related operations.

  PostgreSQL + pgvector               Stores relational commerce data and
                                      supports vector-based product
                                      retrieval.

  Redis                               Supports workflow checkpointing and
                                      background-processing
                                      infrastructure.

  Outbox worker                       Delivers persisted audit events
                                      asynchronously and retries failed
                                      deliveries.

  Payment integration                 Supports checkout and
                                      payment-status confirmation using
                                      the configured payment provider.
  -----------------------------------------------------------------------

The diagram is a logical overview. Deployable service names and exact
boundaries are defined by the Docker Compose configuration in the
repository.

------------------------------------------------------------------------

## Shopping workflow

A typical shopping request follows this high-level flow:

1.  **Understand the request** --- Parse the user's goal, intent,
    product constraints, and budget.
2.  **Retrieve candidates** --- Search the product catalogue using the
    available retrieval tools.
3.  **Compare products** --- Evaluate candidates and select a suitable
    product with a confidence score.
4.  **Route by intent and confidence** --- Low-confidence results are
    retried within a bounded limit. Search and comparison intents do not
    proceed to checkout; explicit purchase or restock intents may.
5.  **Apply the budget guardrail** --- A selected product above the
    user's explicit budget is blocked.
6.  **Attempt checkout** --- The system attempts to create an order for
    the selected product.
7.  **Handle stock failure safely** --- If the selected product is out
    of stock, the agent searches for an eligible in-stock alternative.
    It does not automatically order that alternative.
8.  **Request approval** --- The workflow pauses and asks the user to
    approve or reject the alternative.
9.  **Revalidate and order** --- After approval, the system checks the
    alternative's inventory and budget again before attempting the
    order.
10. **Confirm payment** --- The system checks payment status and can
    retain a pending state when confirmation is not yet available.

### Alternative-product approval

The alternative flow is deliberately designed to avoid purchases the
user did not authorize:

-   Finding an alternative does not create an order.
-   Only an explicit Boolean approval is accepted.
-   Rejection ends the alternative purchase path.
-   Inventory is revalidated after approval because stock may have
    changed while waiting.
-   The alternative is checked against the budget again before order
    creation.

------------------------------------------------------------------------

## Technology stack

The project uses the following technologies in its current
implementation:

  -----------------------------------------------------------------------
  Area                                Technologies
  ----------------------------------- -----------------------------------
  Buyer agent and orchestration       Python, LangGraph, LangChain

  LLM integration                     Google Gemini through the
                                      configured Google GenAI integration

  Tool integration                    Model Context Protocol (MCP)

  Seller/backend services             FastAPI

  Database                            PostgreSQL

  Vector search                       pgvector

  Cache and workflow checkpointing    Redis

  Background processing               Celery / Redis-backed workers, as
                                      configured by the services

  Payments                            Razorpay test-mode integration

  Containers                          Docker, Docker Compose

  Testing                             pytest, pytest-asyncio
  -----------------------------------------------------------------------

Check the service-specific dependency files for the exact installed
package versions.

------------------------------------------------------------------------

## Reliability and safety

### Budget enforcement

The budget guardrail is deterministic. If an explicit budget is provided
and the selected product price exceeds it, the workflow records a
failure and does not proceed to checkout.

If no explicit budget is provided, this guardrail does not impose a
price ceiling.

### Bounded confidence retries

The buyer workflow retries low-confidence interpretation/comparison
results only up to its configured retry limit. If confidence remains
below the threshold, the workflow ends with a low-confidence failure
instead of continuing to purchase.

### Payment confirmation

Order creation and payment confirmation are treated as separate stages.
The confirmation flow handles paid, pending, failed, missing-order, and
status-service-error outcomes. A pending payment is not reported as
paid.

### Redis-backed checkpoints

The LangGraph workflow uses Redis checkpointing for persistent state,
including interrupt-and-resume approval flows.

### Transactional audit outbox

Audit events are persisted to an outbox before asynchronous delivery.
The worker includes:

-   Batch claiming with `FOR UPDATE SKIP LOCKED`.
-   Retry scheduling with backoff.
-   Maximum-attempt handling and dead-letter status.
-   Recovery of expired processing locks.
-   Heartbeats to renew active claims.
-   Graceful shutdown handling.

These mechanisms improve delivery reliability; they do not imply that
every external integration is guaranteed to be available at all times.

------------------------------------------------------------------------

## Repository structure

The repository is a multi-service project. The following is a simplified
view; consult the actual folders for the current implementation.

``` text
shopagent-mcp/
├── buyer_agent/
│   ├── nodes/                 # Buyer-agent workflow nodes
│   ├── scenarios/             # Scenario definitions and examples
│   ├── services/              # Buyer-agent services
│   ├── tests/                 # pytest tests and manual test runners
│   ├── tools/                 # MCP and commerce tool integrations
│   ├── api.py                 # Buyer-agent API
│   ├── audit.py               # Audit event/outbox integration
│   ├── graph.py               # LangGraph workflow definition
│   ├── outbox_worker.py       # Transactional outbox worker
│   ├── state.py               # Shared workflow state
│   ├── pytest.ini             # pytest configuration
│   └── requirements.txt
├── seller_service/            # Seller-side service (if present)
├── database/                  # Database migrations and seed resources
├── docker-compose.yml
└── README.md
```

Some folder names above are illustrative. Use the actual repository tree
as the source of truth if it differs.

------------------------------------------------------------------------

## Getting started

### Prerequisites

-   Docker Desktop with Docker Compose
-   Git
-   API credentials for the external services enabled in your local
    configuration

### 1. Clone the repository

``` bash
git clone https://github.com/kanishqdhangar/shopagent-mcp
cd shopagent-mcp
```

### 2. Configure environment variables

Review the environment-variable references in the service configuration
and Docker Compose file.

Create local environment files from the repository's example files if
provided. Add the required database, Redis, LLM, and payment-provider
configuration.

Do not commit real credentials or local `.env` files.

### 3. Start the services

From the repository root:

``` bash
docker compose up --build -d
```

Check service status:

``` bash
docker compose ps
```

View logs for a service:

``` bash
docker compose logs -f <service-name>
```

Use the service names defined in `docker-compose.yml`.

### 4. Initialize the database

Apply the migrations and seed data using the instructions and scripts
provided in the `database/` and service directories. The exact commands
depend on the migration and seed tooling configured in this checkout.

### 5. Stop the services

``` bash
docker compose down
```

To remove persisted Compose volumes as well (this permanently deletes
local container data):

``` bash
docker compose down -v
```

------------------------------------------------------------------------

## Running the tests

The buyer-agent pytest suite is configured in `buyer_agent/pytest.ini`.

Start the required Redis service if it is not already running:

``` bash
docker compose up -d redis
```

Run the buyer-agent tests from the repository root:

``` bash
docker compose run --rm --no-deps buyer-agent pytest tests/ -v
```

The current verified suite contains **43 passing tests**. It covers:

-   Checkout and alternative-product handling.
-   Explicit approval and rejection.
-   Budget guardrails.
-   Confidence retries.
-   Payment confirmation outcomes.
-   Redis-backed interrupt/resume checkpoint behavior.
-   Stock-failure workflow behavior.

Some older files in the test directory are manual test runners and are
not necessarily collected by pytest.

The Redis checkpointer currently emits a dependency deprecation warning
in the test environment. The verified test run completed successfully
despite these warnings.

------------------------------------------------------------------------

## Example scenarios

The following are representative behaviors covered by the implemented
workflow and tests:

  -----------------------------------------------------------------------
  Scenario                            Expected behavior
  ----------------------------------- -----------------------------------
  User searches for a product         Products can be retrieved and
                                      compared without creating an order.

  User requests a purchase within     The workflow can proceed to
  budget                              checkout.

  Selected product exceeds explicit   The budget guardrail blocks
  budget                              checkout.

  Selected product is out of stock    The agent looks for an eligible
                                      alternative and waits for user
                                      approval.

  User rejects the alternative        No alternative order is created.

  User approves the alternative       Inventory and budget are
                                      revalidated before order creation.

  Payment remains pending             The workflow does not incorrectly
                                      mark the payment as paid.

  Confidence remains too low          The workflow stops after its
                                      bounded retry policy.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## Configuration and secrets

Keep credentials outside source control.

Typical configuration categories include:

-   PostgreSQL connection settings.
-   Redis connection settings.
-   LLM provider API key and model configuration.
-   Payment provider test credentials and webhook secret.
-   Internal service URLs and MCP connection settings.

The exact variable names are defined by the current service
configuration and Compose files. Do not assume that names in this list
are literal environment-variable names.

For local development:

-   Use test/sandbox payment credentials.
-   Never commit API keys, webhook secrets, access tokens, or populated
    `.env` files.
-   Rotate any credential that has accidentally been pushed to a public
    repository.

------------------------------------------------------------------------

## Current scope and limitations

ShopAgent is an actively developed project. The implemented workflows
and passing tests demonstrate specific behaviors, but they are not a
substitute for a full production-readiness review.

Before production use, review at least:

-   Authentication, authorization, and tenant isolation.
-   API validation, rate limiting, and abuse protection.
-   Payment-provider configuration, webhook security, and
    reconciliation.
-   Database backups, migrations, and recovery procedures.
-   Observability, alerting, and operational dashboards.
-   Load, concurrency, and failure testing across all services.
-   Deployment secrets, network policies, and infrastructure security.

Some user-facing functionality and integrations may remain incomplete.
Refer to the current code and service configuration for the exact
implementation status.

## Author

**Kanishq Dhangar**

Software Developer | Backend & AI Systems

- GitHub: [@kanishqdhangar](https://github.com/kanishqdhangar)
- Project: [ShopAgent](https://github.com/kanishqdhangar/shopagent-mcp)

Built as a project exploring agentic AI, distributed systems,
MCP-based integrations, and reliable commerce workflows.