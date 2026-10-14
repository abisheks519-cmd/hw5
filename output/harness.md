# Campus Customs — Harness

How the Campus Customs back office works, end to end:
- **The database:** every table and field, and why it matters to the agents.
- **The MCP tools:** the agents' only way to that data.
- **The five-agent PydanticAI team.**
- **The FastAPI backend and its routes.**
- **The React dashboard**, where a person approves money.
- **The audit trail, the safety rules, and the final run.**

**Contents**

| Section                                           | Read it for                                                                                                                  |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| [Tables](#tables)                                 | Every table and field, and why it matters                                                                                    |
| [How the tables connect](#how-the-tables-connect) | Keys and shared codes between tables                                                                                         |
| [MCP tools](#mcp-tools)                           | All 15 tools (14 for agents, plus `approve_transaction` for people), the tables each reads and writes, which agents use them |
| [Agent team](#agent-team)                         | The five agents: models, prompts, tools, hand-offs, and the agent loop                                                       |
| [Audit trail](#audit-trail)                       | What output/audit_trail.json records for every loop step                                                                     |
| [Safety](#safety)                                 | Customer privacy, real customers and money, token-use limits                                                                 |
| [API routes](#api-routes)                         | The FastAPI backend: every route, one line each                                                                              |
| [Dashboard](#dashboard)                           | The React agent desk: what it shows and how approvals work                                                                   |
| [Final run (Problem 9)](#final-run-problem-9)     | Tickets 101–103 through the dashboard, approvals, and the cash check                                                         |
| [Running the team](#running-the-team)             | Commands                                                                                                                     |

**Database files**

| File                         | Role                                                                                                                  |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `data/campus_customs.db`     | Original, as given. Never changed.                                                                                    |
| `data/campus_customs_new.db` | Working copy. Only the MCP server (`mcp_server/server.py`) opens it; the agents read and update it through MCP tools. |

**Tables at a glance**

| # | Table                               | Holds                                      | Rows at start |
| - | ----------------------------------- | ------------------------------------------ | ------------- |
| 1 | [`desk`](#1-desk)                   | Shop's date and notes                      | 1             |
| 2 | [`tickets`](#2-tickets)             | Incoming requests (the agents' work queue) | 3             |
| 3 | [`inventory`](#3-inventory)         | Stock on hand by size                      | 10            |
| 4 | [`pricing`](#4-pricing)             | Cost and selling price per product         | 4             |
| 5 | [`vendors`](#5-vendors)             | Suppliers                                  | 3             |
| 6 | [`invoices`](#6-invoices)           | Bills from vendors                         | 1             |
| 7 | [`leases`](#7-leases)               | Rent on the shop space                     | 1             |
| 8 | [`cash_accounts`](#8-cash_accounts) | Money the shop has                         | 1             |
| 9 | [`payments`](#9-payments)           | Money paid out (starts empty)              | 0             |

---

## Tables

### 1. desk

**Why it matters for the agents:** Sets the shop's "today" (2026-08-31), so the agents judge due dates, overdue bills and ticket age against the shop's date, not the real clock.

| Field        | Type | Key / rule | What it holds               |
| ------------ | ---- | ---------- | --------------------------- |
| `date_today` | TEXT | Required   | The shop's current date     |
| `notes`      | TEXT | Optional   | Free-text notes for the day |

### 2. tickets

**Why it matters for the agents:** This is the agents' to-do list: each open ticket (a customer order, a rent notice, a discount request) is a job an agent has to read, route and resolve.

| Field        | Type    | Key / rule                   | What it holds                                                      |
| ------------ | ------- | ---------------------------- | ------------------------------------------------------------------ |
| `id`         | INTEGER | PK                           | Ticket number                                                      |
| `type`       | TEXT    | Required                     | Kind of request: `customer_order`, `rent_notice`, `price_override` |
| `requester`  | TEXT    | Required                     | Who asked (customer, landlord, student group)                      |
| `subject`    | TEXT    | Required                     | Short title of the request                                         |
| `sku`        | TEXT    | Optional                     | Product involved, if any                                           |
| `size`       | TEXT    | Optional                     | Size requested, if any                                             |
| `qty`        | INTEGER | Optional                     | Units requested, if any                                            |
| `lease_id`   | INTEGER | FK → `leases.id`, optional   | Lease the ticket is about, if any                                  |
| `invoice_id` | INTEGER | FK → `invoices.id`, optional | Vendor invoice tied to the ticket, if any                          |
| `status`     | TEXT    | Required                     | Where the ticket stands (all start `open`)                         |
| `notes`      | TEXT    | Optional                     | Details of the request                                             |
| `created_at` | TEXT    | Required                     | When the ticket came in (ISO time, Eastern)                        |

### 3. inventory

**Why it matters for the agents:** Tells the agents what is actually on the shelf, by size and aisle, so they can confirm an order or say it is out of stock.

| Field      | Type    | Key / rule       | What it holds                           |
| ---------- | ------- | ---------------- | --------------------------------------- |
| `sku`      | TEXT    | PK (with `size`) | Product code                            |
| `name`     | TEXT    | Required         | Product name                            |
| `size`     | TEXT    | PK (with `sku`)  | `S`, `M`, `L`, `XL`, or `OS` (one size) |
| `qty`      | INTEGER | Required         | Units on hand                           |
| `location` | TEXT    | Required         | Aisle where it is stored                |

### 4. pricing

**Why it matters for the agents:** Gives the agents each product's cost and list price, so they can quote prices and check that any discount still leaves a profit.

| Field        | Type | Key / rule | What it holds                                |
| ------------ | ---- | ---------- | -------------------------------------------- |
| `sku`        | TEXT | PK         | Product code (same codes as `inventory.sku`) |
| `unit_cost`  | REAL | Required   | What the shop pays per unit ($)              |
| `list_price` | REAL | Required   | What the customer pays per unit ($)          |

### 5. vendors

**Why it matters for the agents:** Tells the agents who to reorder from and how many days delivery takes, so restock promises are realistic.

| Field       | Type    | Key / rule | What it holds               |
| ----------- | ------- | ---------- | --------------------------- |
| `id`        | INTEGER | PK         | Vendor number               |
| `name`      | TEXT    | Required   | Vendor name                 |
| `specialty` | TEXT    | Required   | What they supply            |
| `lead_days` | INTEGER | Required   | Days from order to delivery |

### 6. invoices

**Why it matters for the agents:** Shows the agents what the shop owes each vendor and when it is due, so bills get paid on time and only once.

| Field         | Type    | Key / rule                  | What it holds                 |
| ------------- | ------- | --------------------------- | ----------------------------- |
| `id`          | INTEGER | PK                          | Invoice number                |
| `vendor_id`   | INTEGER | FK → `vendors.id`, required | Vendor who sent the bill      |
| `amount`      | REAL    | Required                    | Amount owed ($)               |
| `due_date`    | TEXT    | Required                    | Date payment is due           |
| `status`      | TEXT    | Required                    | Payment state (starts `open`) |
| `description` | TEXT    | Optional                    | What the bill is for          |

### 7. leases

**Why it matters for the agents:** Holds the rent amount and next due date, so the agents can plan cash around the shop's biggest fixed bill.

| Field          | Type    | Key / rule | What it holds           |
| -------------- | ------- | ---------- | ----------------------- |
| `id`           | INTEGER | PK         | Lease number            |
| `space_name`   | TEXT    | Required   | The rented space        |
| `landlord`     | TEXT    | Required   | Who the rent is paid to |
| `monthly_rent` | REAL    | Required   | Rent per month ($)      |
| `next_due`     | TEXT    | Required   | Next rent due date      |
| `notes`        | TEXT    | Optional   | Free-text notes         |

### 8. cash_accounts

**Why it matters for the agents:** This is the shop's money. Agents read it to check whether a bill can be paid (`get_cash_position`, `prepare_payment`), but only a person's approval changes it (`approve_transaction`), and never below zero.

| Field     | Type | Key / rule | What it holds             |
| --------- | ---- | ---------- | ------------------------- |
| `name`    | TEXT | PK         | Account name              |
| `balance` | REAL | Required   | Current balance ($)       |
| `date`    | TEXT | Required   | Date the balance is as of |

### 9. payments

**Why it matters for the agents:** This is the record of every payment and the person who approved it. Agents never write here. A row is added only when a person approves a prepared transaction on the dashboard, so this table is the spending audit trail (empty at the start).

| Field         | Type    | Key / rule | What it holds                                                        |
| ------------- | ------- | ---------- | -------------------------------------------------------------------- |
| `id`          | INTEGER | PK         | Payment number                                                       |
| `kind`        | TEXT    | Required   | What was paid, e.g. an invoice or rent                               |
| `ref_id`      | INTEGER | Optional   | id of the bill being paid (an invoice or lease, depending on `kind`) |
| `amount`      | REAL    | Required   | Amount paid ($)                                                      |
| `account`     | TEXT    | Required   | Cash account it came from (a `cash_accounts.name`)                   |
| `paid_at`     | TEXT    | Required   | When it was paid                                                     |
| `approved_by` | TEXT    | Required   | Who signed off on the payment                                        |

---

### 10. pending_transactions (added by the MCP server)

**Why it matters for the agents:** This is the approval queue. Agents put payments and reorders here with `prepare_payment` and `prepare_purchase`. Cash only moves when a person approves one on the dashboard. The table isn't in the original database: the MCP server creates it the first time something is prepared, and a reset removes it with everything else.

| Field                                      | Type           | Key / rule                                 | What it holds                                                          |
| ------------------------------------------ | -------------- | ------------------------------------------ | ---------------------------------------------------------------------- |
| `id`                                       | INTEGER        | PK                                         | Transaction number shown on the dashboard                              |
| `kind`                                     | TEXT           | Required: `invoice`, `rent`, or `purchase` | What kind of money movement it is                                      |
| `ref_id`                                   | INTEGER        | Optional                                   | `invoices.id` or `leases.id` being paid; empty for a purchase          |
| `ref_due`                                  | TEXT           | Optional                                   | The bill's due date when it was prepared (stops rent being paid twice) |
| `sku`, `size`, `qty`, `vendor_id`          | TEXT / INTEGER | Purchase only                              | What to reorder and from whom                                          |
| `amount`                                   | REAL           | Required                                   | Dollars: the exact bill, or qty × `pricing.unit_cost` for a purchase   |
| `description`                              | TEXT           | Required                                   | One line shown on the Approve card                                     |
| `ticket_id`                                | INTEGER        | Optional                                   | Ticket it came from                                                    |
| `prepared_by`                              | TEXT           | Required                                   | Agent that prepared it                                                 |
| `prepared_at`                              | TEXT           | Required                                   | Shop date when it was prepared                                         |
| `status`                                   | TEXT           | Required: `pending` or `approved`          | Only `pending` can be approved                                         |
| `approved_by`, `approved_at`, `payment_id` | TEXT / INTEGER | Set on approval                            | Who approved it, when, and the `payments.id` it created                |

A unique index allows only one pending transaction per bill (`kind`, `ref_id`), so the same invoice or rent can't wait in the queue twice.

## How the tables connect

| From                              | To                           | Link                                      |
| --------------------------------- | ---------------------------- | ----------------------------------------- |
| `invoices.vendor_id`              | `vendors.id`                 | Foreign key                               |
| `tickets.invoice_id`              | `invoices.id`                | Foreign key                               |
| `tickets.lease_id`                | `leases.id`                  | Foreign key                               |
| `tickets.sku` + `size`            | `inventory.sku` + `size`     | Same codes (not enforced)                 |
| `inventory.sku`                   | `pricing.sku`                | Same codes (not enforced)                 |
| `payments.ref_id`                 | `invoices.id` or `leases.id` | Depends on `kind` (not enforced)          |
| `payments.account`                | `cash_accounts.name`         | Same names (not enforced)                 |
| `pending_transactions.payment_id` | `payments.id`                | Set when a person approves (not enforced) |
| `pending_transactions.ref_id`     | `invoices.id` or `leases.id` | Depends on `kind` (not enforced)          |

SQLite only enforces the foreign keys when `PRAGMA foreign_keys = ON` is set on the connection.

---

## MCP tools

Agents never move money. They prepare payments and purchases, which only queue them in `pending_transactions`, and a person approves them through the backend. `approve_transaction` exists only on the backend's own MCP connection: its server process is started with `CC_HUMAN_APPROVALS=1`. So the agents' connection, and Claude Code, never even see the tool.

The agents reach the database **only** through the campus-customs MCP server (`mcp_server/server.py`, FastMCP). They have no other data tools. `backend/mcp_connection.py` starts the server from its `.mcp.json` entry, and each agent gets a filtered view that shows only the tools its job needs. Every value comes from `data/campus_customs_new.db`, plus simple arithmetic on stored values (margins, totals, days until due). An unknown SKU, size, or id returns an error that lists the real ones.

| Tool                        | Kind                            | Reads tables                                                          | Writes tables                                                                                 | Used by                                         | Tickets                       |
| --------------------------- | ------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------- | ----------------------------- |
| `check_inventory`           | read                            | `inventory`                                                           | —                                                                                             | Inventory, Customer Service                     | 101, 103                      |
| `get_rent_due`              | read                            | `leases`, `desk`                                                      | —                                                                                             | Facilities, Accounting                          | 102                           |
| `get_pricing`               | read                            | `pricing`                                                             | —                                                                                             | Accounting, Customer Service                    | 103                           |
| `list_open_tickets`         | read                            | `tickets`, `desk`                                                     | —                                                                                             | Boss, and the runner when it picks tickets      | all                           |
| `get_ticket`                | read                            | `tickets`                                                             | —                                                                                             | all five agents                                 | all                           |
| `get_invoice`               | read                            | `invoices`, `vendors`, `desk`                                         | —                                                                                             | Inventory, Accounting                           | 101                           |
| `list_vendors`              | read                            | `vendors`                                                             | —                                                                                             | Inventory                                       | 101, 103                      |
| `get_cash_position`         | read                            | `cash_accounts`, `invoices`, `vendors`, `leases`, `desk`              | —                                                                                             | Accounting                                      | 102                           |
| `check_discount`            | read                            | `pricing`                                                             | —                                                                                             | Accounting                                      | 103                           |
| `update_ticket`             | write                           | `tickets`, `desk`                                                     | `tickets` (status, notes)                                                                     | Boss                                            | all                           |
| `list_tickets`              | read                            | `tickets`, `desk`                                                     | —                                                                                             | the backend (`GET /api/tickets`)                | all                           |
| `prepare_payment`           | write (queue only, no money)    | `invoices`, `vendors`, `leases`, `cash_accounts`, `desk`              | `pending_transactions`                                                                        | Accounting                                      | 101 (invoice 501), 102 (rent) |
| `prepare_purchase`          | write (queue only, no money)    | `inventory`, `pricing`, `vendors`, `cash_accounts`, `desk`            | `pending_transactions`                                                                        | Inventory                                       | 101, 103 (reorders)           |
| `list_pending_transactions` | read                            | `pending_transactions`                                                | —                                                                                             | the backend (`GET /api/transactions`)           | all                           |
| `approve_transaction`       | write, moves money (human only) | `pending_transactions`, `invoices`, `leases`, `cash_accounts`, `desk` | `payments`, `cash_accounts`, `invoices` or `leases`, `pending_transactions`, `tickets` (note) | **No agent.** Only the backend's approval route | 101–103                       |

### New tools (Problem 5)

* **`list_open_tickets()`** returns every ticket not marked `resolved`, plus the shop date. The Boss and the runner use it to find the work (101, 102, 103 at the start).
* **`get_ticket(ticket_id)`** returns one ticket row: requester, SKU/size/qty, linked `lease_id`/`invoice_id`, status, and notes. Every agent can read the ticket it was handed.
* **`get_invoice(invoice_id)`** returns an invoice with its vendor's name, specialty, and `lead_days`, and days until due. For 101 it shows invoice 501: a $840 rush reprint of the size S tee from Bulldog Print Co, 5-day lead time, 3 days overdue.
* **`list_vendors()`** returns all vendors with what they supply and their lead times, so Inventory can name a reorder source for a shortage (the 12 hoodies missing on 103).
* **`get_cash_position()`** returns cash on hand next to every open invoice and rent due within a month. For 102: $3,400 cash, $840 open invoice, $2,400 rent, $160 left if all are paid.
* **`check_discount(sku, quantity, discount_pct)`** tests a discount against `pricing`. It returns the new unit price, the totals, the margin left, and `below_cost`. For 103, 10% off 20 hoodies is $52.20 each ($1,044), still $30.20 above cost. It calculates only; it doesn't approve.
* **`update_ticket(ticket_id, status, note, author)`** is the only way ticket status changes. The status must be one of `open`, `in_progress`, `waiting_on_stock`, `waiting_on_approval`, `resolved`, and the author must be one of the five agents. It appends a dated, signed line (`[2026-08-31 boss: open -> waiting_on_stock] ...`) and keeps the earlier notes. Emails, phone numbers, and card numbers are removed, and notes are capped at 600 characters.
### Tools added in Problem 7 (prepare, then a person approves)

* **`list_tickets()`** returns every ticket, open or resolved, plus the shop date. The backend uses it for the ticket list.
* **`prepare_payment(kind, ref_id, prepared_by, ticket_id)`** queues an invoice or rent payment for approval. It does not move money.
  * The amount is taken from the bill itself.
  * It refuses an invoice that's already paid, or rent more than 10 days before it's due.
  * Preparing the same bill again returns the transaction already waiting (`already_prepared`) instead of adding a duplicate.
* **`prepare_purchase(sku, size, qty, vendor_id, prepared_by, ticket_id)`** queues a vendor reorder for approval. Its cost is qty × `pricing.unit_cost`, and it changes neither cash nor stock.
* **`list_pending_transactions(status)`** lists the queue (`pending`, `approved`, or `all`) and the pending total.
* **`approve_transaction(transaction_id, approved_by)`** is the only tool that changes cash, and only the backend's approval route can call it. In one database transaction it:
  * re-checks the bill
  * refuses anything already approved, so a double click never pays twice (tested with four simultaneous clicks: one payment)
  * refuses an agent name as the approver, and any payment larger than the checking balance
  * adds the `payments` row and takes the money out of checking
  * marks the invoice paid, moves the lease's `next_due` forward a month, or pays the vendor for a reorder (stock arrives later)
  * adds a signed note to the ticket

  Errors start with a code: `not_found`, `already_approved`, `conflict`, `insufficient_funds`, or `invalid`.
* `record_payment` (Problem 5) was removed. Agents can no longer pay anything themselves.

### The first 3 tools in detail (Problem 3)

#### 1. `check_inventory(sku, size?)`

* **Reads:** `inventory` (`qty` and `location` for each `sku` + `size`).
* **Unlocks ticket:** 101, Tauhid Zaman's customer order for 1 Classic Bulldog Tee (`CC-TEE-WHITE`) in size S.
* **Why it's the right tool:** Ticket 101 asks for 1 `CC-TEE-WHITE` in size S, and `inventory` is the only table that tracks units per size, so this tool is how the agent sees that size S has 0 on hand in Aisle B before it promises Tauhid Zaman a shirt.
* **Also used for:** ticket 103, where it shows only 8 size M `CC-HOOD-NAVY` hoodies on hand for the 20 requested.
* **Returns:** the product name; `qty`, `location`, and `in_stock` for each size; and `total_qty`.

#### 2. `get_rent_due(lease_id)`

* **Reads:** `leases` (`monthly_rent`, `landlord`, `next_due`) and `desk` (`date_today`, the shop's date).
* **Unlocks ticket:** 102, the rent notice from Elm City Properties, which links `lease_id` 1.
* **Why it's the right tool:** Ticket 102 is the landlord's email saying rent is due in 2 days, and it links `lease_id` 1, so this tool reads that lease's $2,400.00 rent and 2026-09-02 due date from `leases` and counts the 2 days from the shop date in `desk` instead of trusting the email.
* **Returns:** `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`, `shop_date`, and `days_until_due` (negative means overdue).

#### 3. `get_pricing(sku, quantity=1)`

* **Reads:** `pricing` (`unit_cost` and `list_price`).
* **Unlocks ticket:** 103, the Yale AI Club's request for a bulk discount on 20 `CC-HOOD-NAVY` hoodies in size M.
* **Why it's the right tool:** Ticket 103 asks for a bulk discount on 20 `CC-HOOD-NAVY` hoodies, and `pricing` is the only table with both the $58.00 list price and the $22.00 unit cost, so this tool gives the agent the $36.00-per-unit margin ($1,160.00 at list vs. $440.00 cost for 20) that any discount has to stay within.
* **Returns:** `unit_cost`, `list_price`, `margin_per_unit`, `margin_pct`, `quantity`, `list_total`, and `cost_total`.

---

## Agent team

Five PydanticAI agents live under `backend/`:
- **Agent definitions:** one file per agent in `backend/agents/`, each setting its model, prompt, MCP tools, and output type.
- **Prompts:** one file per agent in `backend/prompts/`.
- **Data types:** `backend/models.py`.
- **Agent loop and hand-offs:** `backend/team.py`.
- **Command line:** `backend/run_team.py`.

| Agent            | Files                                                       | Model (course gateway)         | Job                                                                                                | MCP tools                                                                                                            | Returns            |
| ---------------- | ----------------------------------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------------------ |
| Boss             | `agents/boss.py`, `prompts/boss.md`                         | `gpt-6-luna`, reasoning medium | Reads each ticket, hands off the work, combines the answers, records the status                    | `list_open_tickets`, `get_ticket`, `update_ticket`                                                                   | `TicketOutcome`    |
| Inventory        | `agents/inventory.py`, `prompts/inventory.md`               | `gpt-6-luna`, reasoning low    | Stock by size and aisle, shortages, vendors, lead times; prepares reorders for a person to approve | `get_ticket`, `check_inventory`, `list_vendors`, `get_invoice`, `prepare_purchase`                                   | `SpecialistReport` |
| Accounting       | `agents/accounting.py`, `prompts/accounting.md`             | `gpt-6-luna`, reasoning low    | Cash, bills, prices, discounts; prepares payments for a person to approve                          | `get_ticket`, `get_cash_position`, `get_invoice`, `get_rent_due`, `get_pricing`, `check_discount`, `prepare_payment` | `SpecialistReport` |
| Facilities       | `agents/facilities.py`, `prompts/facilities.md`             | `gpt-6-luna`, reasoning low    | The shop space, the lease, the landlord                                                            | `get_ticket`, `get_rent_due`                                                                                         | `SpecialistReport` |
| Customer Service | `agents/customer_service.py`, `prompts/customer_service.md` | `gpt-6-luna`, reasoning low    | Reply drafts for customers and groups (never sent)                                                 | `get_ticket`, `check_inventory`, `get_pricing`                                                                       | `SpecialistReport` |

**Delegation (full connectivity).** Every agent has an `ask_<name>` tool for each of the other four, which makes 20 hand-off routes. A hand-off runs the teammate's own agent loop and returns its `SpecialistReport` (or `TicketOutcome`). Two rules stop runaway hand-offs:
- An agent can't ask a teammate who is already working on the same request higher up the chain, so `boss -> inventory -> boss` is refused.
- A chain can be at most 3 agents long (`boss -> facilities -> accounting`).

Refused hand-offs are logged as `delegate_refused`. The `ask_*` tools carry only requests and reports; all shop data still comes from MCP.

**Prompts.** Each agent's instructions are put together in this order:
1. `prompts/team_rules.md`: rules for every agent: where facts come from, how hand-offs work, and the safety rules (privacy, real customers and money, token use).
2. `prompts/shop_rules.md`: the shop-wide numbers (low stock 5, bulk 10+, up to 10% off without approval and never past 20%, $100 cash floor, $500 warning, rent at most 10 days early, replies within 1 business day, reorder = waiting + 10) and the list of decisions that always go to the owner.
3. The agent's own prompt file: one detailed prompt per agent, covering its job, its tools, how it works step by step, the shop rules for its part of the work, what it hands back, and what is out of its scope. Examples: the Boss's routing and statuses, Inventory's reorder rules, Accounting's bill order, payment and discount rules, Facilities' rent rules, and Customer Service's writing rules.
4. A generated list of the agent's MCP tools and teammates.

**Data types (`backend/models.py`).**
- **Agent outputs:** `TicketOutcome` (Boss) and `SpecialistReport` (the others). Both carry `facts`, where every value names the MCP tool it came from, plus `approvals_needed`, `reply_draft`, and `open_questions` or `next_steps`.
- **Run settings:** `TeamLimits` (token and loop limits) and `TeamDeps` (run id, ticket id, delegation chain).
- **Logging:** `AuditRecord` (one audit-trail line).
- **Name lists:** `AgentName`, `TicketStatus`.

**Agent loop (`Team.run_agent`).** Each agent runs PydanticAI's loop step by step with `agent.iter()`:
- **Model request:** the prompt or tool results go to the model.
- **Model response:** the model replies with text and/or tool calls.
- **Tool calls:** each call is streamed and run (an MCP tool or an `ask_*` hand-off), and its result goes back to the model.
- **Repeat or finish:** the loop continues until the model returns its typed output.

Every step is appended to the audit trail. All agents working on one ticket share one `RunUsage`, so the limits below cap the whole ticket.

**Models.** Every agent runs on `gpt-6-luna`, reached through the course Portkey gateway with `PORTKEY_API_KEY` from the course `.env`.
- **Enforced:** `backend/llm.py` stops the run before a request is sent if the model is anything else or `PORTKEY_API_KEY` is missing. There's no override.
- **Retries:** the OpenAI client retries a failed request up to 6 times with exponential backoff, with a 120-second timeout per request. This was added in Problem 9 after a gateway HTTP 500 stopped one run.
- **Served as `gpt-6-luna-global`:** the gateway returns that name, and the audit trail's `model_response` records show it.
- **Reasoning effort:** medium for the Boss, low for the specialists, to save tokens.
- **Responses API:** needed because Azure refuses tools plus reasoning on `/chat/completions`.

**How the team handled the open tickets.** These are the real results of the final run (Problem 9), started from the dashboard on the reset working database; details in [Final run (Problem 9)](#final-run-problem-9):

| Ticket             | Hand-offs                                       | Result                                                                                                                                                                                                                                     |
| ------------------ | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 101 customer order | Boss -> Inventory, Boss -> Customer Service     | `resolved`. Size S has 0 on hand (M 5, L 3, XL 2). The reply offers M, L, or XL with no date. Invoice 501 ($840, overdue) was reported but not prepared or raised for the owner, so there was no cash change.                              |
| 102 rent notice    | Boss -> Facilities -> Accounting                | `resolved`. Lease 1 is $2,400, due 2026-09-02. Accounting prepared transaction #1, and the owner approved it on the dashboard: checking $3,400 → $1,000, next due 2026-10-02.                                                              |
| 103 bulk discount  | Boss -> Inventory, Accounting, Customer Service | `resolved` (after a retry: the first attempt hit a gateway 500). 8 of 20 on hand. Inventory prepared reorder #2 (22 × $22 = $484), and the owner approved it: checking $1,000 → $516. The reply offers $52.20 each (10% bulk, above cost). |

---

## Audit trail

`output/audit_trail.json` records every agent-loop step, written by `backend/audit.py`.
- **Append-only:** it is one JSON array, and each new record replaces the closing `]`. Earlier records and earlier runs are never rewritten, and the file stays valid JSON.
- **Locked:** a file lock keeps two writers from clashing.
- **Refuses rather than overwrites:** if the file doesn't end in `]`, the writer won't touch it rather than lose history.

Every record has `ts`, `run_id` (one per ticket run; `dashboard` for approvals and resets), `ticket_id`, `agent` (an agent name, `team` for the backend, `human` for the person at the dashboard), `chain`, `step`, `action`, `tool`, `inputs`, `result`, `error`, and `detail` (model, tokens, stop reason, limits, database).

| `action`                       | Logged when                                                                                                          |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `run_start`                    | An agent starts a task (inputs: the task)                                                                            |
| `model_request`                | The loop sends the prompt or tool results to the model                                                               |
| `model_response`               | The model answers (text, the tool calls it wants, tokens, stop reason)                                               |
| `tool_call` / `tool_result`    | An MCP tool is called with its inputs, and returns                                                                   |
| `tool_error`                   | An MCP tool refuses or fails (for example, a payment without approval)                                               |
| `delegate` / `delegate_result` | An agent asks a teammate, and the teammate's report comes back                                                       |
| `delegate_refused`             | A hand-off would loop back or pass the chain limit                                                                   |
| `run_end`                      | An agent finishes (result: its final output, plus the ticket's usage so far)                                         |
| `error`                        | A run stops (model error, limit reached)                                                                             |
| `approval`                     | A person approved a prepared transaction on the dashboard (inputs: transaction id and approver; result: the receipt) |
| `reset`                        | A person reset the database to its original values from the dashboard                                                |

Emails, phone numbers, and card numbers are masked in every record, and any text longer than 2,000 characters is cut.

---

## Safety

### Customer privacy

* Each agent sees only the MCP tools its job needs. For example, Customer Service has no cash, invoice, or vendor tools.
* The prompts say to use a customer's details only for their own ticket, never to mention one customer to another, and to keep costs, cash, bills, and shelf locations out of replies.
* `update_ticket` removes emails, phone numbers, and card numbers before saving a note, and the audit trail masks them too.
* The MCP server process gets only `PATH` and its own settings, never the model key.

### Real customers and real money

* Nothing is sent. Customer, landlord, and group replies are drafts (`reply_draft`) for a person to review and send, and no tool contacts anyone.
* Money moves only when a person approves it.
  * Agents can only prepare payments and purchases (`prepare_payment`, `prepare_purchase`), which queue them in `pending_transactions`.
  * The dashboard's Approve button calls `POST /api/transactions/{id}/approve`, which runs `approve_transaction` on the backend's own MCP connection. No agent's connection has that tool.
  * Approval pays only the exact bill, never twice (pending → approved happens inside one locked database transaction, and repeat clicks get 409), and never more than the balance.
* Agents may offer only the discounts the shop rules allow (up to 10% off on bulk orders of 10+ units). Bigger discounts, delivery dates, holds, and refunds go to the owner. `check_discount` flags any price below cost, and the shop rules forbid selling below it.
* Only the Boss changes a ticket's status.
* The write tools were tested on throwaway copies, so `data/campus_customs_new.db` is unchanged.

### Approvals on the dashboard

* The Approve button names the exact amount and previews the balance after it. It stays disabled until the person types their name in "Approving as", and it locks while its request is in flight.
* The name typed there is recorded as `approved_by` in `payments` and `pending_transactions`, in the audit trail's `approval` record, and in a signed note on the ticket.
* Reset needs two clicks and is refused during a run. The audit trail is never cleared; the reset itself is logged.

### Token-use limits

Limits come from `TeamLimits` in `backend/models.py`. The per-ticket limits are shared by every agent working on that ticket.

| Limit                                 | Value                            |
| ------------------------------------- | -------------------------------- |
| Model requests per ticket             | 30                               |
| Tool calls per ticket (MCP + `ask_*`) | 40                               |
| Input + output tokens per ticket      | 300,000                          |
| Output tokens per model response      | 4,000                            |
| Longest hand-off chain                | 3 agents                         |
| Retries for an invalid final answer   | 2                                |
| Reasoning effort                      | low (specialists), medium (Boss) |

When a limit is hit, that ticket's run stops with an `error` record and the next ticket still runs. The prompts also say to use the fewest tool calls, never repeat a lookup, and keep summaries short. In the final run (Problem 9), ticket 101 used 10 requests and 36,722 input tokens, 102 used 11 and 38,798, and 103 used 16 and 61,405, all well under the 30-request and 300,000-token limits.

---

## API routes

`backend/main.py` is a FastAPI app. Start it from `backend/` with `uvicorn main:app --reload --port 8000`; `GET /docs` shows the interactive docs.
- **Responses:** every route returns JSON. Bad input gets 422, an unknown ticket, run, or transaction gets 404, and a conflict (a run already in progress, an already-approved transaction, not enough cash) gets 409.
- **CORS:** only the Vite dev origins are allowed (`http://localhost:5173` and `http://127.0.0.1:5173`).
- **Data access:** all shop data goes through the backend's MCP connection. Only the reset touches the database file directly.

| Method | URL                                  | Purpose                                                                                                                                                                                   |
| ------ | ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/`                                  | Service info and the list of routes                                                                                                                                                       |
| GET    | `/api/health`                        | Whether the agent team and MCP server are ready, which database is in use, and any run in progress                                                                                        |
| GET    | `/api/tickets`                       | Tickets 101–103 with their status, `state` (open/resolved), and latest run                                                                                                                |
| POST   | `/api/tickets/{ticket_id}/run`       | Runs the agent team on one ticket in the background and returns 202 with a `run_id` (`?wait=true` blocks). One run at a time (409 otherwise). A finished run marks the ticket `resolved`. |
| GET    | `/api/runs`                          | Recent runs, newest first (`?ticket_id=` filters)                                                                                                                                         |
| GET    | `/api/runs/{run_id}`                 | One run's status and outcome, plus each agent's contribution: who asked it, what it said, the tools it used, and what it handed back                                                      |
| GET    | `/api/events`                        | Recent audit-trail events with a readable `message` (what each agent said, tool calls and results, hand-offs, errors). Filters: `ticket_id`, `run_id`, and `after` for polling.           |
| GET    | `/api/transactions`                  | Prepared payments and purchases. `?status=` can be `pending` (default), `approved`, or `all`.                                                                                             |
| POST   | `/api/transactions/{txn_id}/approve` | A person approves one (body `{"approved_by": "Name"}`). This is the only route that changes cash; a repeat click gets 409.                                                                |
| GET    | `/api/cash`                          | The checking balance from `cash_accounts`                                                                                                                                                 |
| POST   | `/api/reset`                         | Restores `data/campus_customs_new.db` to an exact copy of `data/campus_customs.db` (refused during a run). The audit trail is kept and the reset is logged.                               |

## Dashboard

`frontend/` is a React + Vite + TypeScript app (`npm run dev` from `frontend/`, http://localhost:5173). It talks only to the backend at http://localhost:8000, and everything it shows is live data. The full design write-up is in `output/design.md`.

| Area          | What it shows                                                                                                                                                                                                             | Backend routes                                                                  |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Ticket queue  | Tickets 101–103 with Open / Agents working / Resolved / Run failed pills (icon + word) and a "n of 3 resolved" bar                                                                                                        | `GET /api/tickets`                                                              |
| Ticket stage  | The selected ticket, the **Start the agent team** button (locked while running or resolved), a crew strip, a RESOLVED stamp, and the team map (all 20 routes faint, used hand-offs as arrows in the asking agent's color) | `POST /api/tickets/{id}/run`                                                    |
| Activity feed | Each agent's messages, hand-offs, tool calls, results, refusals, and errors, polled every 1.2 s during a run                                                                                                              | `GET /api/events?run_id=…&after=…`                                              |
| Who did what  | The Boss's wrap-up, plus a card per agent: who asked it, its summary, tools used, hand-offs, what it prepared, reply drafts                                                                                               | `GET /api/runs/{run_id}`                                                        |
| Money desk    | The checking balance (flashes when it changes), Approve cards (amount, description, preparing agent, balance after), and a cash log (start − approvals = now)                                                             | `GET /api/cash`, `GET /api/transactions`, `POST /api/transactions/{id}/approve` |
| Masthead      | Shop date, backend/team status light, and **Reset database** (two clicks)                                                                                                                                                 | `GET /api/health`, `POST /api/reset`                                            |

Each agent keeps one identity everywhere: Boss violet star, Inventory green-teal box, Accounting blue ledger, Facilities orange building, Customer Service pink speech bubble. The name always sits next to the color.

There are loading skeletons, an offline banner, inline errors, and toasts. The board refreshes every 5 s.

## Final run (Problem 9)

The working database was reset from the dashboard, then tickets 101, 102, and 103 were started from the dashboard in that order, with no reset between them. The owner approved each prepared transaction on the dashboard. Everything below comes from the real run.

| Step                                       | What happened                                                                                                                                                   | Checking               |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| Reset (04:15:35 UTC)                       | Dashboard → `POST /api/reset`; the working copy is byte-identical to `data/campus_customs.db`                                                                   | $3,400.00              |
| Ticket 101 (`run-a0236cd3e59c`)            | Boss → Inventory → Customer Service; resolved; nothing prepared                                                                                                 | $3,400.00 ($0)         |
| Ticket 102 (`run-eeeec8c6eb4f`)            | Boss → Facilities → Accounting; Accounting prepared #1 (rent $2,400.00); resolved; the owner approved #1 at 04:21:12 UTC (payment 1)                            | $1,000.00 (−$2,400.00) |
| Ticket 103, attempt 1 (`run-96da750f17a3`) | Failed on the Boss's first model request (gateway HTTP 500); nothing prepared                                                                                   | $1,000.00 ($0)         |
| Ticket 103, retry (`run-194e1dae42af`)     | Boss → Inventory, Accounting, Customer Service; Inventory prepared #2 (22-hoodie reorder, $484.00); resolved; the owner approved #2 at 04:31:32 UTC (payment 2) | $516.00 (−$484.00)     |
| **Check**                                  | $3,400.00 + $0.00 − $2,884.00 = **$516.00**, which equals `cash_accounts.balance`; `payments` holds 2 rows summing to $2,884.00                                 | ✓                      |

**Retries and fixes, documented:**
- **The first approval didn't register.** The first Approve attempt on #1 sent no request, most likely because the button was still disabled without a name. A second, step-by-step attempt went through.
- **Ticket 103 needed a retry.** The first attempt died on a gateway 500. The model client now retries up to 6 times with backoff (`backend/llm.py`), and the retry finished in about 20 minutes because the gateway was hanging on some requests.
- **Ticket 102 was fast because of caching.** It took 3 seconds because Portkey returned cached model responses for prompts identical to an earlier run. Its MCP tool calls still ran live.

**Still open:** invoice 501 ($840.00 to Bulldog Print Co, overdue since 2026-08-28) wasn't prepared during ticket 101, so it is still unpaid.

**Prompt change after the run:** to close that gap, I added an "Unpaid vendor invoices" section to `backend/prompts/shop_rules.md` and one routing line to `backend/prompts/boss.md`. The new rules say:
- nothing ships, or gets promised to a customer, while a linked vendor invoice is unpaid
- an open invoice on a ticket always goes to Accounting, which prepares the payment if cash allows and otherwise tells me the shortfall

Both additions are marked in the files. The runs above used the earlier prompts, and I did not re-run them, so the Actual sections, Cash tab, and audit trail still match the database.

**Output files:**

| File                           | What it holds                                                           |
| ------------------------------ | ----------------------------------------------------------------------- |
| `output/desk_tickets.html`     | Expected vs Actual for each ticket, plus the itemized Cash tab          |
| `output/resolved_tickets.json` | Each ticket's final status, outcome, agent contributions, and approvals |
| `output/resolved_board.html`   | Embedded dashboard screenshots of each resolved ticket                  |
| `output/audit_trail.json`      | Every step, appended to the earlier runs                                |

## Running the team

From the `HW 5` folder:

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m backend.run_team --db /path/to/a/copy.db         # try it on a copy first
.venv/bin/python -m backend.run_team                                 # every open ticket, on data/campus_customs_new.db
.venv/bin/python -m backend.run_team --ticket 102
.venv/bin/python -m backend.run_team --agent inventory --task "How many CC-HOOD-NAVY size M are on hand?"
```

A run on the default database changes ticket statuses and notes, and may prepare payments or purchases. Nothing is paid until a person approves it through the API.

To run the whole system, start the backend from `backend/` and the dashboard from `frontend/` in a second terminal:

```bash
source ../.venv/bin/activate
uvicorn main:app --reload --port 8000     # backend: http://localhost:8000
```

```bash
cd frontend && npm install && npm run dev  # dashboard: http://localhost:5173
```
