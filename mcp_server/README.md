# Campus Customs MCP Server

## What it is for

This is the one place every Campus Customs agent gets its data. Agents never open the database themselves:
- The PydanticAI team in `backend/` and the Claude Code vibe coder both reach it only by calling the tools on this server.
- Each tool reads (or, for the two write tools, updates) the database and returns only what is stored there.

That way no agent can make up a stock count, a balance, a rent amount, or a price.

It is built with [FastMCP](https://gofastmcp.com) (`fastmcp` 4.1) and runs over stdio: the agent starts it as a subprocess and talks to it over standard in/out.

## Database it uses

| | |
| --- | --- |
| File | `data/campus_customs_new.db` (the working copy made in Problem 2) |
| Where it's set | `DB_PATH` in `server.py`, found relative to this folder so the server works from any directory. Set `CC_DB_PATH` to use another file (the tests use throwaway copies). |
| Read tools | Open the file read-only (SQLite `mode=ro`), so they can't change it |
| Write tools | Open it with `mode=rw`, which never creates a new file, and make each change in one transaction |
| Not used | `data/campus_customs.db`, the original, which stays untouched |

## The tools (14 for agents, plus 1 for the human approval route)

| Tool | Inputs | Reads | Writes | Returns |
| --- | --- | --- | --- | --- |
| `check_inventory` | `sku`, optional `size` | `inventory` | — | Product name; `qty`, `location`, and `in_stock` for each size; `total_qty` |
| `get_rent_due` | `lease_id` | `leases`, `desk` | — | Space, landlord, `monthly_rent`, `next_due`, notes, shop date, `days_until_due` |
| `get_pricing` | `sku`, optional `quantity` | `pricing` | — | `unit_cost`, `list_price`, margin per unit and %, list and cost totals |
| `list_open_tickets` | — | `tickets`, `desk` | — | Shop date and every ticket not `resolved` |
| `get_ticket` | `ticket_id` | `tickets` | — | The ticket row: requester, SKU/size/qty, linked lease/invoice, status, notes |
| `get_invoice` | `invoice_id` | `invoices`, `vendors`, `desk` | — | Amount, due date, status, description, vendor name/specialty/lead days, `days_until_due` |
| `list_vendors` | — | `vendors` | — | Every vendor's name, specialty, and lead days |
| `get_cash_position` | — | `cash_accounts`, `invoices`, `vendors`, `leases`, `desk` | — | Cash per account, open invoices, rent due within 31 days, and cash left after paying all of it |
| `check_discount` | `sku`, `quantity`, `discount_pct` | `pricing` | — | Discounted unit price and total, what the customer saves, margin left, `below_cost` |
| `update_ticket` | `ticket_id`, `status`, `note`, `author` | `tickets`, `desk` | `tickets` | The updated ticket |
| `list_tickets` | — | `tickets`, `desk` | — | Shop date and every ticket, open or resolved |
| `prepare_payment` | `kind` (`invoice`/`rent`), `ref_id`, `prepared_by`, optional `ticket_id` | `invoices`, `vendors`, `leases`, `cash_accounts`, `desk` | `pending_transactions` | The queued transaction (amount taken from the bill), `already_prepared`, the balance now and if approved. **No money moves.** |
| `prepare_purchase` | `sku`, `size`, `qty`, `vendor_id`, `prepared_by`, optional `ticket_id` | `inventory`, `pricing`, `vendors`, `cash_accounts`, `desk` | `pending_transactions` | The queued reorder (qty × unit cost), `already_prepared`, the balance now and if approved. **No money moves.** |
| `list_pending_transactions` | optional `status` (`pending`/`approved`/`all`) | `pending_transactions` | — | The queue, newest first, and the pending total |
| `approve_transaction` (human connection only) | `transaction_id`, `approved_by` | `pending_transactions`, `invoices`, `leases`, `cash_accounts`, `desk` | `payments`, `cash_accounts`, `invoices` or `leases`, `pending_transactions`, `tickets` | Receipt: payment id, balance before and after, what changed, and a warning under $500 |

Examples on the starting data:
- `check_inventory("CC-TEE-WHITE", "S")`: 0 on hand in Aisle B (ticket 101).
- `get_rent_due(1)`: $2,400 due 2026-09-02, in 2 days (ticket 102).
- `get_cash_position()`: $3,400 cash, $840 open invoice, $2,400 rent, so $160 left.
- `check_discount("CC-HOOD-NAVY", 20, 10)`: $52.20 each, $1,044 total, $30.20 margin per unit (ticket 103).

Margins, totals, and day counts are simple arithmetic on stored values. If a SKU, size, or id isn't in the database, the tool returns an error that lists the real ones (for example `No lease with id 7. Lease ids on file: 1.`).

### Rules the write tools enforce

- **`update_ticket`**
  - The status must be `open`, `in_progress`, `waiting_on_stock`, `waiting_on_approval`, or `resolved`, and `author` must be one of the five agents.
  - It appends one dated, signed line (`[2026-08-31 boss: open -> waiting_on_stock] ...`) and never deletes earlier notes.
  - It removes emails, phone numbers, and card numbers, and caps notes at 600 characters.
- **`update_ticket`** also accepts the author `dashboard`. The backend uses it when it marks a finished run's ticket `resolved`.
- **`prepare_payment` and `prepare_purchase`** only add a row to `pending_transactions`; neither changes cash.
  - `prepare_payment` takes the amount from the bill, refuses an invoice that's already paid, and refuses rent more than 10 days before it's due.
  - `prepare_purchase` prices the reorder at qty × `pricing.unit_cost`, and only for an item and size the shop already stocks.
  - Preparing the same bill (or the same reorder for the same ticket) again returns the transaction that's already waiting, so nothing is queued twice.
- **`approve_transaction`** is the only tool that moves money.
  - **Who has it:** it exists only on a server started with `CC_HUMAN_APPROVALS=1`. Only the FastAPI backend's own connection does that, for the dashboard's Approve button. The agents' connection and Claude Code never see the tool.
  - **One locked transaction:** in a single database transaction, with SQLite's write lock held, it:
    1. Refuses a transaction that isn't `pending`. A second click, even at the same moment, gets `already_approved`, and nothing is charged again.
    2. Re-checks that the invoice is still open, or that the rent for that due date hasn't been paid.
    3. Refuses an agent name as `approved_by`, and any amount larger than the checking balance.
    4. Adds the `payments` row and takes the money out of checking.
    5. Marks the invoice `paid` or moves the lease's `next_due` forward one month. A purchase just pays the vendor; stock arrives after the lead time.
    6. Marks the transaction `approved` and adds a signed note to the ticket.
  - **Error codes:** every error starts with `not_found`, `already_approved`, `conflict`, `insufficient_funds`, or `invalid`, which the backend turns into HTTP 404, 409, or 422.

## How to run it

From the `HW 5` folder:

```bash
python3 -m venv .venv
.venv/bin/pip install -r mcp_server/requirements.txt
source .venv/bin/activate

python mcp_server/server.py                       # start the server (stdio)
fastmcp list mcp_server/server.py                 # show the 14 agent-facing tools
fastmcp call mcp_server/server.py check_inventory sku=CC-TEE-WHITE size=S
fastmcp call mcp_server/server.py get_cash_position
fastmcp call mcp_server/server.py check_discount sku=CC-HOOD-NAVY quantity=20 discount_pct=10
```

Activate the venv before running `fastmcp list` or `fastmcp call`, because they start the server with the `fastmcp` command on your PATH. `fastmcp call` on a write tool changes the database, so point `CC_DB_PATH` at a copy when you try those.

| Setting | Effect |
| --- | --- |
| `CC_DB_PATH` | Use this database file instead of `data/campus_customs_new.db` |
| `CC_HUMAN_APPROVALS` | `1` adds `approve_transaction`. Only the FastAPI backend sets this, on its own connection. |

## Who connects to it

- **The agent team (`backend/`).**
  - **Connection:** `backend/mcp_connection.py` starts the server using the `.mcp.json` entry. It passes only `PATH` and `CC_DB_PATH`, never `CC_HUMAN_APPROVALS`, so the agents can only prepare money movements.
  - **Tool access:** each agent sees only its own subset of the tools (see `output/harness.md`, "Agent team").
- **The FastAPI backend (`backend/main.py`).** It has its own connection, with `CC_HUMAN_APPROVALS=1`. It reads tickets, cash, and the approval queue, and runs `approve_transaction` when a person clicks Approve.
- **Claude Code.**
  - **Connection:** `.mcp.json` registers the server as `campus-customs`, and `.claude/settings.local.json` approves it. Any Claude Code session started in `HW 5` connects at startup.
  - **Prompts:** the three original read tools run without asking. The newer tools ask first, so a write never happens without you seeing it.
  - **Test results:** `output/mcp_smoke.json` holds the Problem 4 checks of the original 3 tools.

## Files

| File | What it is |
| --- | --- |
| `server.py` | The FastMCP server: 14 agent-facing tools plus `approve_transaction` for the human approval route |
| `requirements.txt` | Python dependency (`fastmcp`) |
| `README.md` | This file |
