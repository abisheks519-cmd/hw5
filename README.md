# Campus Customs Agent Desk (MGT 409, HW 5)

Campus Customs is a small campus merch shop. In this project, five AI agents run its back office:

- a **Boss** agent reads each ticket and hands the work to **Inventory**, **Accounting**, **Facilities**, and **Customer Service**
- every shop fact comes from a SQLite database through an **MCP server**
- a **React dashboard** shows the agents working

Agents can only *prepare* payments and purchases. No money moves until a person clicks **Approve**.

## What's in the repo

| Path | What it is |
| --- | --- |
| `data/campus_customs.db` | The original database. It is never changed. |
| `data/campus_customs_new.db` | The working copy that the MCP server, agents, and dashboard use. |
| `mcp_server/server.py` | FastMCP server (stdio). It is the only way the agents read or change shop data. Tools are listed in `mcp_server/README.md`. |
| `.mcp.json` | How to start the MCP server. Claude Code and the backend both use it. |
| `backend/` | The PydanticAI agent team, see the next table. |
| `frontend/` | The React + Vite + TypeScript dashboard. |
| `output/` | Homework deliverables, see the last table. |
| `AI_prompts.md` | The prompts I typed into Claude for each problem. |

What's in `backend/`:

| File or folder | What it is |
| --- | --- |
| `team.py` | Runs the agent team |
| `agents/` | One file per agent |
| `prompts/` | One prompt per agent, plus the shared shop rules |
| `main.py` | FastAPI backend |
| `models.py` | Data types |
| `audit.py` | Writes the audit trail |
| `llm.py` | Model setup |

What's in `output/`:

| File | What it is |
| --- | --- |
| `harness.md` | The tables, MCP tools, agents, API routes, and safety rules |
| `desk_tickets.html` | Expected plan, Actual run, Cash, and Reflection tabs. Opens directly in a browser. |
| `resolved_board.html` | Dashboard screenshots of the resolved tickets |
| `resolved_tickets.json` | Each ticket's status, outcome, agent contributions, and approvals |
| `audit_trail.json` | Every agent step from every run |
| `mcp_smoke.json` | MCP tool checks |
| `design.md` | Dashboard design notes |

## What you need

- **Python 3 and Node.js.** I used Python 3.14 and Node 24.
- **A course Portkey API key.** All five agents use `gpt-6-luna` through the course Portkey gateway.
- **A terminal on macOS or Linux.** Run the commands from the project root unless a step says otherwise.

## 1. One-time setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env            # then paste your key after PORTKEY_API_KEY=
cd frontend && npm install && cd ..
```

The virtual environment has to be named `.venv` and sit in the project root, because `.mcp.json` starts the MCP server with `.venv/bin/python`. `.gitignore` leaves `.env` out, so the real key never gets committed.

## 2. Copy the original database for a clean run

Runs change `data/campus_customs_new.db`: ticket statuses, prepared and approved payments, and the checking balance. To start over from the original values, stop the backend first, then copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

If the backend is already running, use the dashboard's Reset button instead (step 6). It does the same copy safely while the app is up.

## 3. Start the MCP server

```bash
.venv/bin/python mcp_server/server.py
```

The server talks over stdio, so it sits quietly waiting for a client. Press Ctrl+C to stop it. You usually don't need to keep it running in a terminal of its own, because:

- the backend starts its own copy from `.mcp.json` when it boots
- Claude Code does the same

To use the tools from Claude Code, run `claude` in the project root, approve the `campus-customs` server when asked, and type `/mcp` to see its tools.

## 4. Start the FastAPI backend

```bash
cd backend
source ../.venv/bin/activate
uvicorn main:app --reload --port 8000
```

Check http://localhost:8000/api/health. It should show `"ok":true` and `"team_ready":true`. The backend only accepts browser requests from the dashboard at http://localhost:5173.

## 5. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The dashboard expects the backend at http://localhost:8000. If yours runs somewhere else, set `VITE_API_BASE` before running `npm run dev`.

## 6. Reset, then run all three tickets

1. **Reset the database before a full three-ticket run.** Either click **Reset database** in the top bar and then **Click again to reset**, or run:

   ```bash
   curl -X POST http://localhost:8000/api/reset
   ```

   Checking goes back to **$3,400.00** and tickets 101, 102, and 103 are open again. The audit trail is never cleared; the reset is just logged in it.
2. **Run a ticket.** Pick it in the queue and click **Start the agent team**. The team map and activity feed show who handed work to whom and which MCP tools they called.
3. **Approve any money moves.** If the agents prepare a payment or purchase, it waits on the money desk on the right. Type your name in **Approving as** and click **Approve**. This is the only step that moves cash, and each transaction can only be paid once.
4. **Run 101, then 102, then 103** without resetting in between. In my run, checking went from $3,400 to $1,000 after the rent payment (ticket 102), then to $516 after the hoodie reorder (ticket 103).

You can also run the team without the dashboard:

```bash
.venv/bin/python -m backend.run_team --ticket 102
```

The agents work the ticket the same way, but anything they prepare still needs the dashboard's Approve button.

## Safety

- **The key stays private.**
  - The real `.env` is never committed. `.env.example` only shows the variable name.
  - The key is sent only to Portkey, and the MCP server process never receives it.
- **Agents can't move money.**
  - Accounting can only prepare payments, and Inventory can only prepare purchases.
  - Cash changes only through `POST /api/transactions/{id}/approve`, which is the dashboard's Approve button.
- **Customer details are masked in the audit trail.** Every agent step is appended to `output/audit_trail.json`, with emails, phone numbers, and card numbers removed.
- **Each ticket has a budget.** Model requests, tool calls, and tokens are capped per ticket, so a stuck run stops instead of running up cost.

## Optional settings

Set these as environment variables in your terminal. Leave them unset to use the defaults.

| Variable | Default | What it changes |
| --- | --- | --- |
| `CC_DB_PATH` | `data/campus_customs_new.db` | Which database the backend and MCP server use |
| `CC_AUDIT_PATH` | `output/audit_trail.json` | Where agent steps are logged |
| `CC_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Which dashboard addresses the backend accepts |
| `VITE_API_BASE` | `http://localhost:8000` | Where the dashboard looks for the backend |
