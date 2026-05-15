# The Problem: Revenue That Quietly Walks Out the Door

## Background

Service agencies — marketing shops, recruitment firms, dev-shop retainers, bookkeeping practices — share a structural weakness: revenue collection is almost always managed reactively. A client misses a payment, someone notices eventually, an awkward email goes out, and the client pays if they feel like it. There is no systematic follow-up, no escalating sequence, no intelligent deduplication of the contacts driving those sequences. The result is a slow, invisible revenue haemorrhage that only becomes visible when someone runs the numbers.

The larger an agency grows, the worse this gets. A 200-client book-of-business that sends a single invoice email and never follows up is leaving money on the table every single month. The number is rarely dramatic on any one invoice — it is death-by-a-thousand-cuts.

## Three Silent Drains

### 1. Overdue invoices that don't get a second nudge

Most CRM or invoicing tools send one automated reminder. Maybe two. Then the job falls to a human who is already context-switching across three other accounts. Invoices age past 30, 60, 90 days not because the client refuses to pay but because nobody sent the right message at the right time with the right tone. A well-structured recovery sequence — Day 3, Day 7, Day 14, Day 30, escalate-to-principal — will close the majority of genuinely collectable overdue invoices. Without it, agencies typically recover fewer than half of invoices that age past 30 days.

### 2. Failed recurring charges that slip through

Subscription retainers are the healthiest revenue model a service agency can run — right up until a client's card declines at renewal and the system quietly does nothing. Payment processors retry once or twice on their own schedule; most CRMs never surface the failure prominently. The client is still receiving service, the agency is not being paid, and by the time anyone notices the account is two months in arrears and the conversation is uncomfortable. An automated retry sequence paired with an immediate alert is a solved problem — but it has to be wired up deliberately.

### 3. Duplicate and dirty contacts

Automation breaks on bad data. A contact appears three times under different email addresses; the recovery sequence fires for one, skips the other two, and the client receives either zero nudges or three contradictory ones. Duplicate contacts also inflate pipeline metrics, corrupt churn calculations, and make every reporting dashboard a lie. Deduplication is not glamorous work, but it is the prerequisite for every other automation in this system. Skipping it means building on sand.

## The Source Case: ~$45,000 Recovered

The original version of this system was built as a bespoke n8n implementation for a single service-agency client. The brief was simple: find the money the agency was losing and build automations to stop losing it.

An audit of the client's Go High Level CRM revealed overdue invoice balances spread across dozens of contacts, a material percentage of recurring charges that had failed silently over the preceding six months, and a contact list with significant duplication. A three-stage automation was built: a deduplication pass to clean the contact graph, an overdue-invoice recovery sequence with intelligent escalation, and a failed-payment retry loop with Twilio SMS as the high-urgency channel.

Total recovered across the engagement: approximately $45,000.

That system was n8n-only. This repo is the code-first re-implementation: the same logic, now in typed Python with a proper test harness, a versioned schema, a real API, and a dashboard.

## What This Repo Is

- A FastAPI backend that ingests GHL webhooks, deduplicates contacts, and drives recovery sequences
- A Supabase-backed data layer with Row-Level Security for multi-tenant safety
- A sequence engine that escalates overdue invoices and failed charges through configurable steps
- A Claude-powered insights layer that synthesises recovery status for dashboard consumers
- A Next.js dashboard that shows the AR picture in real time
- A portfolio artefact demonstrating production-grade Python, typed APIs, and AI integration

## What This Repo Is Not

- A white-label product ready to sell to your clients (it handles _your_ agency's AR, not your clients' AR)
- A replacement for a proper accounts-receivable accounting system
- A guaranteed outcome — results depend on client data quality, sequence configuration, and the underlying collectability of the receivables
- Production-ready on Day 1; the application logic ships across Days 2–7 of the build sprint
