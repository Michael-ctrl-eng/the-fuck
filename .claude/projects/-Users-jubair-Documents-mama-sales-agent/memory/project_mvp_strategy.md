---
name: MVP Strategy
description: MVP product strategy — FB-only sellers first, our platform is the CRM, no ongoing website sync
type: project
---

## MVP Strategy (decided 2026-03-31)

**Target customer**: Bangladeshi Facebook page sellers (60-70% have NO website)

**Core principle**: Our platform IS the CRM. No ongoing sync with external websites.

**Product onboarding (priority order)**:
1. FB Ads/Posts extraction (via Graph API) — future, after MVP
2. FB Shop/Catalog API — future, after MVP
3. Website crawl — one-time import only, already built
4. Paste single product URL → auto-extract product
5. Manual entry on dashboard
6. CSV upload

**Why:** Businesses manage stock/price/products on OUR dashboard only. No double work. For businesses with websites, we do a one-time crawl import, then they manage on our platform.

**How to apply:** Don't build ongoing website sync or complex API integrations. Focus on making the dashboard CRM experience perfect. The AI chatbot reads from our DB only.

**Future (post-MVP):** FB Graph API integration, API sync for businesses that have their own systems.
