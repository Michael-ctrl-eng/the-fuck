<p align="center">
  <h1 align="center">Mama Sales Agent</h1>
  <p align="center">
    AI-powered sales chatbot platform for Bangladeshi Facebook pages.
    <br />
    Handles customer conversations in Bangla, Banglish & English via Messenger.
    <br />
    <br />
    <a href="#quick-start">Quick Start</a>
    &middot;
    <a href="#features">Features</a>
    &middot;
    <a href="#api-docs">API Docs</a>
    &middot;
    <a href="#architecture">Architecture</a>
    &middot;
    <a href="#contributing">Contributing</a>
  </p>
</p>

---

## What is Mama Sales Agent?

Mama Sales Agent is an open-source, multi-tenant AI sales chatbot platform built for Bangladeshi e-commerce businesses that sell through Facebook pages. Page owners connect their business, and an AI agent handles customer conversations — answering product questions, collecting orders, and notifying shop owners — all in the customer's preferred language.

**The problem:** Thousands of Bangladeshi small businesses sell through Facebook pages but manually reply to every customer message. They miss orders, respond late, and can't scale.

**The solution:** An AI sales agent that knows your product catalog, speaks Bangla/Banglish/English, collects orders with proper Bangladeshi address formats (Division > District > Upazila), and sends you notifications for every new order.

### Demo Conversation

```
Customer: bhai ekta punjabi lagbe, price koto?

AI Agent: Bhai, ki obostha? 😊
          Amader punjabi teen ta ache stock e:

          1. Cotton Panjabi (সুতি পাঞ্জাবি) - ৳1200 [✅ In Stock]
          2. Fatua (ফতুয়া) - ৳900 [✅ In Stock]
          3. Silk Punjabi (সিল্ক পাঞ্জাবি) - ৳2800 (was ৳3500) [✅ In Stock]

          Tumi konta chen?
```

---

## Features

- **Multi-language AI** — Responds in Bangla (বাংলা), Banglish, or English based on the customer's language
- **Multi-tenant** — Each Facebook page is an isolated tenant with its own products, orders, and conversations
- **Flexible Product Schema** — Products only need name + price. Any extra fields (color, size, brand, RAM, flavor, weight...) are stored as dynamic attributes. Works for clothing, electronics, food, services — anything
- **Product Catalog** — Manual entry, CSV bulk upload (any CSV format auto-detected), or automatic website crawling
- **Website Crawler** — Provide a URL, the system crawls with Katana/trafilatura and extracts products using AI
- **Vectorless RAG** — PageIndex-style knowledge base built from crawled content (no vector DB needed)
- **Order Collection** — AI collects name, phone (BD format validation), full address (Division/District/Upazila), and payment method
- **Order Management** — Full lifecycle: Pending → Confirmed → Shipped → Delivered
- **Messenger Integration** — Facebook Messenger webhook for real customer conversations
- **Duplicate Detection** — Fuzzy product matching (pg_trgm) prevents catalog duplicates across all data sources
- **Notifications** — Email alerts to shop owners on new orders
- **Dashboard** — Minimalistic web UI for managing products, orders, conversations, and testing the AI
- **Swagger API** — Full OpenAPI documentation with interactive testing
- **128 Tests** — Comprehensive unit + integration + system test suite

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9+, FastAPI |
| Database | PostgreSQL 16 (with pg_trgm for fuzzy matching) |
| Cache / Queue | Redis 7, Celery |
| LLM | OpenRouter (free models — Nemotron, Qwen, GPT-OSS) |
| Knowledge Base | PageIndex-style vectorless RAG (no vector DB) |
| Web Crawler | Katana (ProjectDiscovery) + trafilatura fallback |
| Dashboard | Jinja2 templates + Pico CSS |
| Auth | JWT (python-jose) + bcrypt |
| Testing | pytest + pytest-asyncio + aiosqlite |
| Containerization | Docker + Docker Compose |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.9+
- An [OpenRouter](https://openrouter.ai) API key (free tier works)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/mama-sales-agent.git
cd mama-sales-agent
```

### 2. Set up environment

```bash
cp .env.example .env
```

Edit `.env` and add your OpenRouter API key:

```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

### 3. Start infrastructure

```bash
docker-compose up -d db redis
```

This starts PostgreSQL (port 5432) and Redis (port 6379).

### 4. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### 5. Run database migrations

```bash
alembic upgrade head
```

### 6. Seed sample data (optional)

```bash
python seed.py
```

This creates a test user (`jubair@test.com` / `test123`) with a sample Bangladeshi fashion store and 12 products.

### 7. Start the application

```bash
uvicorn app.main:app --reload --port 8000
```

### 8. Open the dashboard

- **Dashboard:** http://localhost:8000/dashboard/login
- **Swagger API:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

Login with the seeded credentials, then click **Test Chat** to start talking to the AI agent.

### Running with Docker (full stack)

```bash
docker-compose up -d
```

This starts all services: PostgreSQL, Redis, the FastAPI app, and the Celery worker.

---

## Running Tests

```bash
# All 120 tests
pytest -v

# Unit tests only (no DB needed)
pytest tests/test_language.py tests/test_phone.py tests/test_bd_address.py tests/test_order_collector.py tests/test_prompts.py tests/test_security.py -v

# Integration tests (uses SQLite)
pytest tests/test_auth.py tests/test_tenants.py tests/test_products.py tests/test_orders.py tests/test_conversations.py tests/test_webhook.py tests/test_crawl.py tests/test_system.py -v

# With coverage
pytest --cov=app --cov-report=html
```

---

## API Docs

Once the app is running, full interactive API documentation is available at:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Login and get JWT token |
| `GET` | `/api/auth/me` | Get current user info |
| `POST` | `/api/tenants` | Create a new business/tenant |
| `GET` | `/api/tenants` | List your businesses |
| `GET` | `/api/tenants/{id}/stats` | Dashboard statistics |
| `POST` | `/api/tenants/{id}/products` | Add a product |
| `POST` | `/api/tenants/{id}/products/upload-csv` | Bulk import from CSV |
| `GET` | `/api/tenants/{id}/products` | List products (paginated, searchable) |
| `GET` | `/api/tenants/{id}/orders` | List orders (filterable by status) |
| `PATCH` | `/api/tenants/{id}/orders/{oid}/status` | Update order status |
| `GET` | `/api/tenants/{id}/conversations` | List customer conversations |
| `GET` | `/api/tenants/{id}/conversations/{cid}` | View full chat history |
| `POST` | `/api/tenants/{id}/crawl` | Start website crawl job |
| `GET` | `/api/webhook/messenger` | Facebook webhook verification |
| `POST` | `/api/webhook/messenger` | Receive Messenger events |
| `POST` | `/api/test/chat` | Test AI agent without Facebook |

---

## Architecture

### High-Level Flow

```
Customer (Messenger/Test Chat)
        │
        ▼
┌─────────────────┐     ┌──────────────┐
│  Webhook / Test  │────▶│  AI Agent    │
│  Chat Endpoint   │     │  (agent.py)  │
└─────────────────┘     └──────┬───────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌──────────────┐  ┌────────────┐  ┌──────────────┐
     │ Product DB   │  │ OpenRouter │  │ Conversation │
     │ (catalog)    │  │ LLM API   │  │ History      │
     └──────────────┘  └────────────┘  └──────────────┘
              │
              ▼
     ┌──────────────┐     ┌──────────────┐
     │ Order Created │────▶│ Notification │
     │ (if confirmed)│     │ (email/SMS)  │
     └──────────────┘     └──────────────┘
```

### Data Pipeline

```
Website URL ──▶ Katana Crawler ──▶ trafilatura (HTML→text) ──▶ LLM Product Extraction ──▶ Products DB
                                                             ──▶ PageIndex Tree (JSON)  ──▶ Knowledge Base
```

---

## Project Structure

```
mama_sales_agent/
│
├── app/                          # Main application package
│   ├── main.py                   # FastAPI app factory, lifespan, route registration
│   ├── config.py                 # Settings via pydantic-settings (reads from .env)
│   ├── database.py               # Async SQLAlchemy engine, session factory, Base class
│   ├── dependencies.py           # FastAPI dependency injection (get_db, get_current_user, get_tenant)
│   │
│   ├── ai/                       # AI / LLM layer
│   │   ├── agent.py              # Core sales agent orchestrator — processes messages, calls LLM,
│   │   │                         #   manages conversations, detects orders, creates them in DB
│   │   ├── llm_client.py         # OpenRouter API client with automatic model fallback and
│   │   │                         #   rate-limit handling (retries with exponential backoff)
│   │   ├── prompts.py            # System prompt templates — sales persona, BD-specific knowledge,
│   │   │                         #   order collection instructions, product catalog formatting
│   │   ├── order_collector.py    # Extracts structured order JSON from AI responses, validates
│   │   │                         #   BD phone numbers, cleans response text for the customer
│   │   └── language.py           # Language detection — classifies input as Bangla (Unicode check),
│   │                             #   Banglish (pattern matching), or English
│   │
│   ├── api/                      # FastAPI route handlers
│   │   ├── router.py             # Top-level router that aggregates all sub-routers
│   │   ├── auth.py               # POST /register, /login, /facebook — JWT token endpoints
│   │   ├── tenants.py            # CRUD for tenants (businesses) + stats endpoint
│   │   ├── products.py           # Product CRUD, CSV upload, search, pagination
│   │   ├── orders.py             # Order listing, detail view, status transitions
│   │   ├── conversations.py      # Conversation list and message history viewer
│   │   ├── crawl.py              # Trigger website crawl jobs, check job status
│   │   ├── webhook.py            # Facebook Messenger webhook — verification (GET) and
│   │   │                         #   event processing (POST). Responds 200 immediately,
│   │   │                         #   processes messages in BackgroundTasks
│   │   ├── facebook.py           # FB page listing, connection, catalog sync via Graph API
│   │   ├── test_chat.py          # POST /api/test/chat — simulate customer messages locally
│   │   │                         #   without needing Facebook. Used by the dashboard chat widget
│   │   └── dashboard.py          # Serves Jinja2 HTML templates for the web dashboard
│   │
│   ├── models/                   # SQLAlchemy ORM models (database tables)
│   │   ├── user.py               # Users table — page owners who log in to the dashboard
│   │   ├── tenant.py             # Tenants table — each connected Facebook page/business.
│   │   │                         #   Stores page_access_token, website_url, notification prefs
│   │   ├── product.py            # Products table — only fixed columns are name, price, is_active,
│   │   │                         #   source. ALL other fields (description, category, color, size,
│   │   │                         #   brand, RAM, weight, flavor, etc.) stored in flexible JSON
│   │   │                         #   `attributes` column. Adapts to any business type
│   │   ├── customer.py           # Customers table — end-users who message via Messenger.
│   │   │                         #   Identified by FB Page-Scoped ID (PSID). Stores collected
│   │   │                         #   address info (division, district, upazila)
│   │   ├── conversation.py       # Conversations table — one active conversation per customer-tenant
│   │   ├── message.py            # Messages table — individual chat messages (role: customer/assistant)
│   │   ├── order.py              # Orders + OrderItems tables — full order with BD address,
│   │   │                         #   payment method (COD/bKash/Nagad), status lifecycle,
│   │   │                         #   line items with product snapshots
│   │   ├── crawl_job.py          # CrawlJobs table — tracks async crawl operations
│   │   │                         #   (status: pending → crawling → indexing → completed/failed)
│   │   └── knowledge_base.py     # KnowledgeBases table — stores PageIndex tree as JSON.
│   │                             #   One active knowledge base per tenant
│   │
│   ├── schemas/                  # Pydantic request/response schemas (serialization layer)
│   │   ├── auth.py               # RegisterRequest, LoginRequest, TokenResponse, UserResponse
│   │   ├── tenant.py             # TenantCreate, TenantUpdate, TenantResponse
│   │   ├── product.py            # ProductCreate, ProductUpdate, ProductResponse, ProductListResponse
│   │   ├── order.py              # OrderResponse, OrderItemResponse, OrderStatusUpdate, OrderListResponse
│   │   ├── conversation.py       # ConversationResponse, MessageResponse, ConversationListResponse
│   │   └── webhook.py            # TestChatRequest, TestChatResponse, CrawlRequest, CrawlJobResponse
│   │
│   ├── services/                 # Business logic layer (called by API routes)
│   │   ├── auth_service.py       # User registration, login (email+password), Facebook OAuth login
│   │   ├── tenant_service.py     # Tenant creation, listing, updates, dashboard stats aggregation
│   │   ├── product_service.py    # Product CRUD with duplicate detection (SKU + fuzzy name matching
│   │   │                         #   via pg_trgm), CSV parsing and bulk import, product context
│   │   │                         #   formatting for AI consumption
│   │   ├── order_service.py      # Order creation with line items, order number generation,
│   │   │                         #   status transition validation (enforces valid state machine)
│   │   ├── messenger_service.py  # Facebook Graph API wrapper — send text messages, quick replies,
│   │   │                         #   and fetch user profiles from Messenger
│   │   ├── notification_service.py # Email notifications for new orders via aiosmtplib.
│   │   │                         #   Sends bilingual (Bangla+English) order summaries
│   │   └── facebook_service.py   # Facebook Graph API — list user's pages, subscribe to webhooks,
│   │                             #   fetch product catalogs from Facebook Shops
│   │
│   ├── tasks/                    # Celery async background tasks
│   │   ├── celery_app.py         # Celery instance configuration (broker: Redis, timezone: Asia/Dhaka)
│   │   ├── crawl_tasks.py        # Full crawl pipeline: Katana/trafilatura crawl → LLM product
│   │   │                         #   extraction → PageIndex knowledge base building. Updates
│   │   │                         #   crawl_job status at each stage
│   │   └── notification_tasks.py # Async order notification dispatch (decoupled from request cycle)
│   │
│   └── utils/                    # Shared utility modules
│       ├── security.py           # JWT token creation/verification, bcrypt password hashing,
│       │                         #   Facebook webhook signature (X-Hub-Signature-256) verification
│       ├── phone.py              # Bangladeshi phone number validation (01XXXXXXXXX format,
│       │                         #   supports +880 prefix) and normalization
│       └── bd_address.py         # Complete Bangladesh administrative hierarchy data:
│                                 #   8 Divisions → 64 Districts → ~500 Upazilas.
│                                 #   Validation, lookup, and reverse-lookup functions
│
├── dashboard/                    # Frontend — server-rendered HTML pages
│   ├── templates/                # Jinja2 HTML templates
│   │   ├── base.html             # Base layout — nav bar, Pico CSS, shared styles (badges,
│   │   │                         #   chat bubbles, stat cards, modals)
│   │   ├── login.html            # Login/Register form with client-side JS (stores JWT in localStorage)
│   │   ├── dashboard.html        # Home page — lists businesses or shows onboarding form to create one
│   │   ├── chat.html             # Test Chat widget — real-time chat UI that calls POST /api/test/chat.
│   │   │                         #   Simulates customer conversations without Facebook
│   │   ├── products.html         # Product management — table view, add product modal, CSV upload
│   │   │                         #   modal with import results, inline delete
│   │   ├── orders.html           # Order management — filterable table, status badges, detail modal
│   │   │                         #   with line items, one-click status transitions
│   │   ├── conversations.html    # Conversation viewer — list of chats, click to see full message
│   │   │                         #   history in a chat bubble UI
│   │   ├── crawl.html            # Website crawler — URL input, depth selector, job status table
│   │   │                         #   with auto-refresh every 10 seconds
│   │   └── settings.html         # Tenant settings — business name, FB page token, website URL,
│   │                             #   notification preferences, quick stats widget
│   └── static/                   # Static assets (CSS/JS — currently using CDN for Pico CSS)
│       ├── css/.gitkeep
│       └── js/.gitkeep
│
├── tests/                        # Test suite (120 tests)
│   ├── conftest.py               # Shared fixtures — test DB (SQLite), test client, test user,
│   │                             #   tenant, products, customer, conversation with messages
│   ├── test_auth.py              # Auth endpoint tests — register, login, duplicate email,
│   │                             #   invalid credentials, JWT validation (9 tests)
│   ├── test_tenants.py           # Tenant CRUD + multi-tenant isolation tests (9 tests)
│   ├── test_products.py          # Product CRUD, search, pagination, CSV upload with errors,
│   │                             #   soft delete (10 tests)
│   ├── test_orders.py            # Order lifecycle, status transitions, invalid transitions,
│   │                             #   cancellation, immutable delivered orders (9 tests)
│   ├── test_conversations.py     # Conversation listing and message history (3 tests)
│   ├── test_webhook.py           # Messenger webhook verification, message receiving,
│   │                             #   edge cases (6 tests)
│   ├── test_crawl.py             # Crawl job creation, listing, detail (4 tests)
│   ├── test_language.py          # Language detection — Bangla, Banglish, English (10 tests)
│   ├── test_phone.py             # BD phone validation — all operators, formats,
│   │                             #   normalization (18 tests)
│   ├── test_bd_address.py        # Address validation — divisions, districts, upazilas,
│   │                             #   hierarchy checks (13 tests)
│   ├── test_order_collector.py   # AI response JSON extraction, field validation,
│   │                             #   response cleaning (7 tests)
│   ├── test_prompts.py           # Prompt generation, product context formatting (6 tests)
│   ├── test_security.py          # JWT creation/decoding, password hashing (6 tests)
│   └── test_system.py            # End-to-end integration tests — full onboarding flow,
│                                 #   order lifecycle, multi-tenant isolation, webhook flow,
│                                 #   dashboard page rendering, Swagger docs (7 tests)
│
├── alembic/                      # Database migration system
│   ├── env.py                    # Alembic environment — loads models, configures DB URL
│   ├── script.py.mako            # Migration file template
│   └── versions/                 # Generated migration files
│       └── 5179285ae0ae_initial_schema.py
│
├── data/                         # Reference data (BD geo data loaded from bd_address.py)
│
├── alembic.ini                   # Alembic configuration
├── docker-compose.yml            # Docker services: PostgreSQL 16, Redis 7, app, celery worker
├── Dockerfile                    # Python 3.12 slim image with all dependencies
├── init.sql                      # PostgreSQL init script — enables pg_trgm extension
├── requirements.txt              # Python dependencies (pinned versions)
├── pytest.ini                    # pytest configuration (asyncio_mode = auto)
├── seed.py                       # Database seeder — creates test user + 12 Bangladeshi products
├── .env.example                  # Environment variable template
└── .gitignore                    # Git ignore rules
```

---

## Database Schema

```
┌──────────┐     ┌──────────┐     ┌───────────┐
│  users   │────▶│ tenants  │────▶│ products  │
│          │  1:N│          │  1:N│           │
└──────────┘     └────┬─────┘     └───────────┘
                      │
              ┌───────┼────────┐
              │       │        │
              ▼       ▼        ▼
        ┌──────────┐  │  ┌──────────────┐
        │customers │  │  │ crawl_jobs   │
        │          │  │  └──────────────┘
        └────┬─────┘  │
             │        ▼
             │  ┌──────────────┐
             │  │knowledge_bases│
             │  └──────────────┘
             ▼
       ┌──────────────┐     ┌──────────┐
       │conversations │────▶│ messages │
       │              │  1:N│          │
       └──────┬───────┘     └──────────┘
              │
              ▼
        ┌──────────┐     ┌─────────────┐
        │  orders  │────▶│ order_items │
        │          │  1:N│             │
        └──────────┘     └─────────────┘
```

### Key Tables

| Table | Purpose |
|-------|---------|
| `users` | Dashboard users (page owners). Auth via email/password or Facebook |
| `tenants` | Each connected business/Facebook page. Stores page token, settings |
| `products` | Product catalog per tenant. Fixed: name + price. Flexible JSON `attributes` for any other fields |
| `customers` | End-customers identified by Messenger PSID. Stores collected address info |
| `conversations` | Chat sessions between customer and AI agent |
| `messages` | Individual messages within conversations (role: customer/assistant) |
| `orders` | Customer orders with BD address hierarchy and payment method |
| `order_items` | Line items per order with product snapshots |
| `crawl_jobs` | Async crawl job tracking with status updates |
| `knowledge_bases` | PageIndex tree stored as JSON per tenant |

---

## Configuration

All configuration is via environment variables (`.env` file). See [`.env.example`](.env.example) for all options.

### Required

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key ([get one free](https://openrouter.ai)) |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_MODEL` | `nvidia/nemotron-3-super-120b-a12b:free` | Primary LLM model |
| `JWT_SECRET_KEY` | `change-me...` | Secret for JWT signing (change in production!) |
| `FB_APP_ID` | — | Facebook App ID (for Messenger integration) |
| `FB_APP_SECRET` | — | Facebook App Secret |
| `FB_VERIFY_TOKEN` | `mama-verify-token` | Webhook verification token |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | — | Email notification settings |

---

## Facebook Messenger Setup

To connect real Facebook pages:

1. Create a Facebook App at [developers.facebook.com](https://developers.facebook.com)
2. Add the Messenger product to your app
3. Generate a Page Access Token with permissions: `pages_messaging`, `pages_show_list`
4. Set your webhook URL to `https://your-domain.com/api/webhook/messenger`
5. Set the verify token to match your `FB_VERIFY_TOKEN` env variable
6. Paste the Page Access Token in the dashboard Settings page

For local development, use the **Test Chat** widget in the dashboard instead — it simulates the full Messenger flow without needing Facebook.

---

## Flexible Product Format

Products only require **name** and **price**. Everything else is stored as flexible attributes — the system adapts to any business type.

### API Examples

```bash
# Clothing store
curl -X POST /api/tenants/{id}/products -d '{
  "name": "Silk Saree", "price": 5000,
  "name_bn": "সিল্ক শাড়ি", "color": "red", "material": "silk", "category": "Saree"
}'

# Electronics store
curl -X POST /api/tenants/{id}/products -d '{
  "name": "Samsung A15", "price": 18000,
  "brand": "Samsung", "RAM": "6GB", "storage": "128GB", "warranty": "1 year"
}'

# Bakery
curl -X POST /api/tenants/{id}/products -d '{
  "name": "Chocolate Cake", "price": 850,
  "flavor": "dark chocolate", "weight": "1kg", "serves": "8-10"
}'

# Grocery
curl -X POST /api/tenants/{id}/products -d '{
  "name": "Miniket Rice", "price": 350,
  "weight": "5kg", "origin": "Dinajpur", "organic": true
}'
```

The AI agent automatically uses whatever attributes you provide when talking to customers.

### CSV Import (Any Format)

Upload **any CSV format**. The system auto-detects columns:

- **Name column** (required): `name`, `product_name`, `title`, or `item`
- **Price column** (required): `price`, `cost`, `amount`, `rate`, or `mrp`
- **Everything else**: stored as product attributes automatically

Example CSVs that all work:

```csv
name,price,category,color,material
Cotton Saree,1500,Clothing,white,cotton
Silk Punjabi,3500,Clothing,blue,silk
```

```csv
product_name,cost,brand,RAM,storage
Samsung A15,18000,Samsung,6GB,128GB
iPhone 13,85000,Apple,4GB,128GB
```

```csv
item,rate,weight,flavor
Chocolate Cake,850,1kg,dark chocolate
Vanilla Pastry,120,150g,vanilla
```

The system reports which columns it detected:

```json
{
  "imported": 3,
  "detected_columns": {
    "name_column": "product_name",
    "price_column": "cost",
    "attribute_columns": ["brand", "RAM", "storage"]
  }
}
```

---

## Order Status Lifecycle

```
pending ──▶ confirmed ──▶ shipped ──▶ delivered
   │            │
   └──▶ cancelled ◀──┘
```

Only valid transitions are allowed. The API returns `400 Bad Request` for invalid transitions (e.g., `pending → delivered`).

---

## Supported Payment Methods

| Method | Code | Notes |
|--------|------|-------|
| Cash on Delivery | `cod` | Default. Most common in Bangladesh |
| bKash | `bkash` | Mobile payment |
| Nagad | `nagad` | Mobile payment |
| Bank Transfer | `bank` | Direct bank transfer |

---

## Bangladesh Address Hierarchy

The system includes complete administrative data for address validation:

- **8 Divisions:** Dhaka, Chittagong, Rajshahi, Khulna, Barisal, Sylhet, Rangpur, Mymensingh
- **64 Districts** mapped to their divisions
- **~500 Upazilas** mapped to their districts

The AI agent collects addresses step by step and validates the hierarchy (e.g., ensures "Dhanmondi" is under "Dhaka" district in "Dhaka" division).

---

## Roadmap

- [ ] Full Facebook OAuth flow (automatic page discovery)
- [ ] bKash / Nagad payment gateway integration
- [ ] WhatsApp Business API support
- [ ] Delivery tracking (Pathao, Steadfast, RedX APIs)
- [ ] Voice message transcription
- [ ] Image-based product search
- [ ] Analytics dashboard (conversion rates, popular products)
- [ ] Multi-language admin dashboard (Bangla UI)
- [ ] SaaS billing system for page owners

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the test suite (`pytest -v`)
5. Commit (`git commit -m 'Add amazing feature'`)
6. Push (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Setup

```bash
# Clone & setup
git clone https://github.com/your-username/mama-sales-agent.git
cd mama-sales-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start services
docker-compose up -d db redis

# Run migrations & seed
alembic upgrade head
python seed.py

# Run the app
uvicorn app.main:app --reload

# Run tests
pytest -v
```

---

## License

This project is open source and available under the [MIT License](LICENSE).

---

<p align="center">
  Built for Bangladeshi businesses with ❤️
  <br />
  <sub>AI-powered commerce in আমাদের ভাষায় (our language)</sub>
</p>
