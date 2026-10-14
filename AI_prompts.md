# HW 5 — AI Prompts Log

This file logs the prompts I typed into Claude for each problem in HW 5, with the follow-ups I needed and what was lacking before each one.

---

## Problem 1: Vibe coder prompts

* **Prompt I typed:** I am working on HW 5 so please save everything in the folder. For problem 1, I will need you to create an AI_prompts.md file that you will keep updating as I work. This file tracks what I typed into the Claude. I need: problem number and title, the prompt I typed, the follow-up prompts if needed (and one sentence on what was lacking after the first prompt). This is exactly what I did for HW 1 and 2 and 3 and 4.
* **Follow-up prompts:** None.
* **What was lacking after the first prompt:** Nothing. The prompt named the file, where to save it, and every field each entry needs, following the format from HW 1 through HW 4.
* **Evidence I worked on the problem:** Created `AI_prompts.md` in the HW 5 folder with the per-problem entry format (problem number and title, prompt typed, follow-up prompts, what was lacking, evidence of work).

---

## Problem 2: Database copy and harness

* **Prompt I typed:** Problem 2: Open the campus customs db file in the folder HW5. Make a copy of this and place it in data/campus_customs_new.db. Later problems will update that copy. I will also need to create a harness.md file in an output folder. For each table, please list the fields and one short line on why that table matters for the agents.
* **Follow-up prompts:** None.
* **What was lacking after the first prompt:** Nothing. The prompt named the source database, the path for the copy, where the harness goes, and what each table entry needs.
* **Evidence I worked on the problem:** Copied `data/campus_customs.db` to `data/campus_customs_new.db` (byte-identical, passes SQLite's integrity check; the original stays unchanged). Created `output/harness.md` covering all 9 tables (`desk`, `tickets`, `inventory`, `pricing`, `vendors`, `invoices`, `leases`, `cash_accounts`, `payments`). Each has a one-line "why it matters for the agents" and an aligned table listing every field with its type, key/rule, and what it holds. The file also has a tables-at-a-glance summary with starting row counts and a table showing how the tables connect.

---

## Problem 3: MCP server and its first 3 tools

* **Prompt I typed:** Problem 3: Please write an MCP server in mcp_server/ using FastMCP. This will talk to data/campus_customs_new.db. Every agent uses tools in the MCP server. Right now, please write 3 tools that will be needed for the tickets in the database. Names should be clear to understand and data used should come from the database. Dont make up any info. In the harness file, list each of the 3 MCP tools. Each tools needs to include: the table it reads, which ticket it helps unlock (101,102,103), and why it is the appropriate tool for the ticket (one sentence). Don't write vague lines. Needs to be specific. I also need a mcp_server/README.md file that explains what the MCP server is for, the database file it uses, and 3 tools it has.
* **Follow-up prompts:** None.
* **What was lacking after the first prompt:** Nothing. The prompt named the framework, folder, and database; asked for 3 ticket-driven tools with clear names and only database data; and listed what the harness and README must say about each tool.
* **Evidence I worked on the problem:** Wrote `mcp_server/server.py` (FastMCP 4.1, stdio) with 3 read-only tools that open `data/campus_customs_new.db` with `mode=ro`. `check_inventory` reads `inventory` for ticket 101 and shows the size S tee has 0 on hand. `get_rent_due` reads `leases` and `desk` for ticket 102 and returns $2,400.00 due 2026-09-02, 2 days from the shop date. `get_pricing` reads `pricing` for ticket 103 and returns the $58.00 list price, $22.00 cost, $36.00 margin per unit, and $1,160.00 vs. $440.00 for 20 hoodies. An unknown SKU, size, or lease id returns an error listing the real ones. Tested by starting the server over stdio and calling every tool with the ticket values; all results matched direct SQL queries, all 5 bad inputs returned errors, and the database was unchanged afterward. Added the MCP tools section to `output/harness.md` (table read, ticket unlocked, and a one-sentence reason for each tool) and wrote `mcp_server/README.md` (purpose, database file, the 3 tools, how to run) and `mcp_server/requirements.txt`.

---

## Problem 4: Connect the MCP server to Claude Code and smoke-test it

* **Prompt I typed:** Problem 4: Please add the MCP server to this claude code. I want the claud vibe coder to call these tools. Save the connection JSON text in .mcp.json at the project root. With the vibe coder connected, please check and test each of the 3 MCP tools. Save the evidence in output/mcp_smoke.json file. For every tool include: the prompt you asked the vibe coder, the tool name, the tool output (values must match in the campus customs db (new).
* **Follow-up prompts:** None.
* **What was lacking after the first prompt:** Nothing. The prompt said where the connection JSON goes, that the vibe coder must call each of the 3 tools, where the evidence goes, and what each tool's entry must contain.
* **Evidence I worked on the problem:** Registered the server with `claude mcp add-json campus-customs … --scope project`, which wrote `.mcp.json` (stdio: `.venv/bin/python mcp_server/server.py`). Approved it and allowed its 3 read-only tools in `.claude/settings.local.json`. A new Claude Code session in HW 5 showed `campus-customs` as connected, with `mcp__campus-customs__check_inventory`, `get_rent_due`, and `get_pricing` available. Ran one fresh Claude Code session per tool, each with a plain-English ticket prompt that didn't name the tool, and with shell and file tools blocked so data could only come through the MCP server. The vibe coder picked the right tool every time: ticket 101 got `check_inventory` (`CC-TEE-WHITE` size S: 0 on hand, Aisle B), ticket 102 got `get_rent_due` (lease 1: $2,400, due 2026-09-02, 2 days), and ticket 103 got `get_pricing` (20 × `CC-HOOD-NAVY`: $22 cost, $58 list, $36 margin, $1,160 vs. $440). Every output field matched a direct SQL query on `data/campus_customs_new.db` (7/7, 8/8, 8/8), and the database was unchanged afterward. Saved the prompts, tool names, inputs, outputs, field-by-field database checks, replies, and session ids in `output/mcp_smoke.json`, and added a "Using it from Claude Code" section to `mcp_server/README.md`.

---

## Problem 5: PydanticAI agent team, new MCP tools, audit trail, and safety

* **Prompt I typed:** Problem 5: Now I need to build the agentic team for Campus Customs with PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they all delegate work to each other with full connectivity. Put the agent prompts in backend/prompts/ (one file per agent). Put data types in backend/models.py. Agent files go under backend/. Please give me info on shop rules that agent needs. I need to write it in my own words but guidance would help. Update the existing agents and MCP server so they can handle the open tickets. Add any needed MCP tools, using data/campus_customs_new.db for all shop facts. Do not create data or create a tools layer that bypasses MCP. Log every agent-loop step to output/audit_trail.json, recording the agent, action, tool inputs, results, and errors. Append records and preserve previous runs. In output/harness.md, list every agent and MCP tool, including new tools, and the database tables each tool uses. Add a short safety section covering customer privacy, actions involving real customers and money, and token-use limits. Update mcp_server/README.md to match the final tool list. Verify the tools and logging work, then briefly summarize the changes and checks.
* **Follow-up prompts:** the portkey needs to use gpt 6 luna. (My first message was cut off after the first sentence, so I re-sent the whole prompt.)
* **What was lacking after the first prompt:** The prompt didn't say which model the agents should use, so Claude picked `gpt-5.6-luna` for the Boss and `gpt-5.4-mini` for the others, and the course requires `gpt-6-luna`.
* **Evidence I worked on the problem:**
  * **MCP server:** grew from 3 to 11 tools in `mcp_server/server.py`. The 6 new read tools are `list_open_tickets`, `get_ticket`, `get_invoice`, `list_vendors`, `get_cash_position`, and `check_discount`. The 2 new write tools are `update_ticket`, which keeps a signed note history and removes personal details, and `record_payment`, which pays only with a person's approval, for the exact amount, never twice, never past the balance, and never rent more than 10 days early.
  * **Agent team:** built in `backend/`. There is one file per agent in `backend/agents/` and one prompt per agent in `backend/prompts/`, plus `team_rules.md` and a `shop_rules.md` template for me to write. Data types are in `backend/models.py`, the step-by-step `agent.iter` loop and the 20 `ask_*` hand-off routes are in `backend/team.py`, and `backend/run_team.py` runs it from the command line.
  * **Data access:** each agent sees only a filtered set of MCP tools. All five agents run on `gpt-6-luna` through the course Portkey gateway. After the follow-up, a check confirmed the gateway serves it as `gpt-6-luna-global` with tools plus reasoning.
  * **Audit trail:** `backend/audit.py` appends every loop step to `output/audit_trail.json` without rewriting earlier runs.
  * **Tool tests:** 24/24 checks passed on throwaway database copies, covering every tool and every payment refusal.
  * **Scripted team test:** 20/20 passed. It showed hand-offs, a refused loop back to the Boss, the 3-agent chain limit, a refused unapproved payment, a blocked tool outside an agent's set, the token budget stopping a run, and earlier audit records preserved byte for byte.
  * **Live runs (rerun on `gpt-6-luna`; all 40 model responses came from `gpt-6-luna-global`):** on database copies, the team handled tickets 101 (waiting on approval: size S has 0 on hand, and paying overdue reprint invoice 501 needs the owner), 102 (waiting on approval; with a test approver it paid the $2,400 rent and resolved the ticket), and 103 (waiting on approval; 8 of 20 on hand, discount needs the owner). Each ticket used 9–12 model requests. Fixed along the way: Azure needed the Responses API, approved payments weren't being made, and agents repeated lookups. `data/campus_customs_new.db` is unchanged.
  * **Documentation:** updated `output/harness.md` (all 11 tools with tables read and written, the agent team, audit trail, safety, how to run), rewrote `mcp_server/README.md` for the 11 tools, and added `requirements.txt`.

---

## Problem 6: Desk tickets page with expected plans

* **Prompt I typed:** Problem 6: Create output/desk_tickets.html, which should open directly in a browser. First, read the project's ticket details, agent roles, and available MCP tools. Create separate tabs for tickets 101, 102, and 103, plus empty Cash and Reflection tabs labeled "Coming later." For each ticket, fill in an Expected section explaining: Which agent the Boss should call first and why. Every delegation I expect, including who delegates to whom, the order, and each agent's responsibility. The specific MCP tools I expect the agents to use and their purpose. Tailor each plan to the ticket. Only involve relevant specialists; avoid sending every agent to every ticket. Use clear, natural language and explain the reasoning behind each plan. Leave an Actual section empty on each ticket tab for results after the agents run. Do not wire the backend or run the agents yet. If you cannot find the ticket descriptions, agent roles, or tool definitions, ask me for the missing information before writing the plans.
* **Follow-up prompts:** None.
* **What was lacking after the first prompt:** Nothing. The prompt named the file, the five tabs, the three things each Expected section must explain, that plans should only bring in the relevant specialists, and that the Actual sections stay empty with the agents not run.
* **Evidence I worked on the problem:**
  * **Inputs read first:** ticket details and their facts through the campus-customs MCP tools (`list_open_tickets`, `check_inventory`, `get_invoice`, `get_rent_due`, `get_cash_position`, `get_pricing`, `check_discount`, `list_vendors`, all read-only); agent roles and tool lists from `backend/agents/`; tool definitions from `mcp_server/server.py`. Nothing was missing, so there was nothing to ask.
  * **Page:** `output/desk_tickets.html` is a single self-contained file with tabs for Ticket 101, 102, 103, Cash, and Reflection (the last two say "Coming later."). A collapsible table at the top lists each agent's job and MCP tools.
  * **Each ticket tab:** the ticket details, then an Expected section covering who the Boss calls first and why, every hand-off in order (the ask, the agent's responsibility, and what it should come back with), the MCP tools expected (who calls them, inputs, purpose, and the value the database should return), the tools not expected, which agents stay out and why, and the expected outcome. An empty Actual section follows.
  * **Ticket 101:** Boss → Inventory → Customer Service. Accounting and Facilities stay out.
  * **Ticket 102:** Boss → Facilities → Accounting. `record_payment` is used only with approval. Inventory and Customer Service stay out.
  * **Ticket 103:** Boss → Inventory → Accounting → Customer Service. Facilities stays out.
  * **Checks:** checked in headless Chrome in light and dark mode, including opening a specific tab from a link. Fixed a rendering glitch where the header disappeared when the page opened on a tab link. The backend was not wired and the agents were not run; `data/campus_customs_new.db` is unchanged.

---

## Problem 7: FastAPI backend

* **Prompt I typed:** Problem 7: Hello I need help implementing the FastAPI backend in `backend/main.py`. First inspect the existing database, agent team, and project structure, then add routes that: Return tickets 101, 102, and 103 with their open/resolved status. Accept a ticket ID and run the agent team on that ticket. Return recent agent events, including what each agent said and which tools it used, so the dashboard can refresh. Approve a prepared payment or purchase only after a human clicks Approve. Agents must only prepare the transaction; this approval route actually changes cash. Prevent duplicate execution. Return the current checking balance from `cash_accounts`. Reset the database to its original values for a fresh run. Use the existing project components and return JSON responses with appropriate validation and error handling. Configure CORS if needed for the React dashboard. Do not build the frontend yet. From `backend/`, start the server with: `uvicorn main:app --reload --port 8000`. Verify the routes work at `http://localhost:8000`. In `output/harness.md`, document each route on one line with its HTTP method, URL, and purpose.
* **Follow-up prompts:** None.
* **What was lacking after the first prompt:** Nothing. The prompt listed every route's job, the money rule (agents only prepare, the approval route changes cash, no duplicates), CORS, the start command, and how to document the routes.
* **Evidence I worked on the problem:**
  * **Agents can only prepare money movements.** Replaced the agents' `record_payment` with `prepare_payment` (Accounting) and `prepare_purchase` (Inventory). They only add a row to a new `pending_transactions` queue.
  * **Only the human route changes cash.** Added `approve_transaction`, which the MCP server registers only when started with `CC_HUMAN_APPROVALS=1`. Only the backend's own connection is started that way, so the agents and Claude Code can't see it. In one locked database transaction it re-checks the bill, refuses anything already approved, refuses an agent name or a payment larger than the balance, then pays and notes the ticket.
  * **Backend:** wrote `backend/main.py` (FastAPI) with JSON routes for health, tickets, starting a run (background, one at a time, 409 if busy), runs with each agent's contribution, events (readable messages and polling), transactions, approve (404/409/422 error codes), cash, and reset (an exact atomic copy of the original database, refused during a run). CORS allows only the Vite origin `http://localhost:5173`.
  * **MCP tests:** 25/25 passed, including four simultaneous approvals of one transaction producing exactly one payment. The scripted team test still passes.
  * **Server test:** started the server from `backend/` with `uvicorn main:app --reload --port 8000`. On a throwaway database copy, ticket 102 ran Boss → Facilities → Accounting in 39 seconds, Accounting prepared transaction 1 ($2,400 rent), and the ticket was marked resolved. A second start during the run got 409. Approving dropped checking from $3,400 to $1,000, and a repeat approval got 409. Reset restored the original. Bad inputs returned 404 or 422, and only the Vite origin got CORS headers.
  * **Fixed along the way:** the first reset used SQLite's backup method, which left the copy differing from the original in one header byte. Switched to an atomic file copy, which is byte-identical.
  * **Real database check:** re-ran the read routes and reset on `data/campus_customs_new.db`, which stayed byte-identical to the original.
  * **Docs:** documented every route on one line in `output/harness.md`, along with the new tools and the `pending_transactions` table. Updated `mcp_server/README.md`, the prompts, and `requirements.txt`.

---

## Problem 8: React agent dashboard

* **Prompt I typed:** Problem 8: Hey I need to build a really nice agent dashboard in `frontend/` using React, Vite, and TypeScript. Inspect the existing project and connect it to the actual backend routes from Problem 7 at `http://localhost:8000`. The dashboard must: List tickets 101, 102, and 103 with their status. Let me select a ticket and start the agent team. Show each agent's messages, actions, and tool use as the ticket runs. Mark the ticket resolved when the run finishes. Show a short summary of each agent's contribution to that ticket. Display pending payments or purchases with a human Approve button connected to the backend approval route. Show the current checking balance and refresh it after approval so the decrease is visible. Use a polished, creative layout with distinct agent identities, clear ticket statuses, readable activity feeds, and prominent approval controls. Include loading and error states, prevent duplicate submissions, and use live backend data. Configure backend CORS to allow the Vite origin, usually `http://localhost:5173`. Start the frontend from `frontend/` using `npm run dev` and verify the complete flow works. Create `output/design.md` explaining the layout, how agents look distinct, how resolved tickets and cash appear, and why the creative design choices make the dashboard enjoyable to use.
* **Follow-up prompts:** None.
* **What was lacking after the first prompt:** Nothing. The prompt listed every feature the dashboard needed, the design goals, the states to handle, the CORS origin, the start command, and what `design.md` must explain.
* **Evidence I worked on the problem:**
  * **Dashboard:** built `frontend/` (React 19 + Vite 8 + TypeScript 7) with a typed client for every backend route.
  * **Layout:** a ticket queue with status pills and a progress bar. A ticket stage with a Start button, a crew strip, and a team map that draws all 20 hand-off routes faintly and lights up the ones used. A live activity feed (messages, hand-offs, tool calls and results, refusals). "Who did what" cards for each agent. A money desk with a balance tile that flashes when it changes, Approve cards that name the amount and preview the balance, and a cash log.
  * **Agent identities:** each of the five agents has its own color, glyph, and role line.
  * **States:** loading skeletons, an offline banner, inline errors, and toasts. Light and dark mode, and reduced motion.
  * **No duplicate submissions:** Start and Approve lock while working, Approve needs your name, and reset takes two clicks.
  * **Backend changes:** a finished run now marks the ticket `resolved` (the Boss's prompt also ends normal runs that way). CORS allows `http://localhost:5173`.
  * **Verified the full flow:** started the backend from `backend/` and the frontend with `npm run dev`, then drove the real dashboard in Chrome with Playwright. On ticket 102 the Start button locked to "Agents working…", the feed filled live, and the ticket flipped to Resolved with the stamp. Contribution cards showed Boss, Facilities, and Accounting. Typing a test name and clicking "Approve $2,400.00" dropped the cash tile from $3,400.00 to $1,000.00, matching `GET /api/cash`. Reset from the UI restored $3,400.00 and all three tickets open. No console errors.
  * **Docs:** wrote `output/design.md`.

---

## Problem 9: Run all three tickets through the dashboard

* **Prompt I typed:** Problem 9: I need to use the existing backend, agents, and React dashboard. Reset `data/campus_customs_new.db` to its original values and record the starting checking balance. Then run tickets 101, 102, and 103 through the dashboard until all are resolved, without resetting between tickets. When a payment or purchase requires human approval, let me approve it through the dashboard before continuing. Update `output/desk_tickets.html`: Preserve each ticket's **Expected** section. Fill each **Actual** section with which agents worked, what they delegated and to whom, and which MCP tools they used, based on the real run. On the **Cash** tab, **itemize the money** in a table showing: Starting checking balance immediately after the reset. Each ticket's payments or purchases, dollar amounts, reasons, and cash changes. Show $0 with an explanation if a ticket caused no cash change. Running balance after each transaction and total cash change per ticket. Ending checking balance, verified against `cash_accounts` in the working database. Clearly show: starting balance + inflows − outflows = ending balance. Also complete: `output/resolved_tickets.json`: each ticket's ID, final status, short outcome, each agent's contribution, and any human approvals. `output/resolved_board.html`: a page that opens directly in a browser containing an actual screenshot of the React dashboard for each resolved ticket. Embed the screenshots so the page is self-contained. `output/audit_trail.json`: append records from the real runs, preserving existing entries. `output/harness.md`: finish documenting the database tables, MCP tools, five agents, API routes, dashboard, and safety rules. Verify all three tickets are resolved and the itemized cash totals match the database. Use actual events, transactions, and screenshots throughout. If something fails, fix the cause and document any retries.
* **Follow-up prompts:** None. (I approved transactions #1 and #2 myself on the dashboard when Claude paused and asked.)
* **What was lacking after the first prompt:** Nothing. The prompt gave the run order, the no-reset rule, the human approval step, and every file and table the results needed.
* **Evidence I worked on the problem:**
  * **Reset:** reset the working database from the dashboard. The starting balance of $3,400.00 matched on the dashboard tile, `GET /api/cash`, and `cash_accounts`, and the file was byte-identical to the original.
  * **Ticket 101** (`run-a0236cd3e59c`): Boss → Inventory → Customer Service, resolved, $0 cash change. Invoice 501 ($840) was reported but not prepared.
  * **Ticket 102** (`run-eeeec8c6eb4f`): Boss → Facilities → Accounting. Accounting prepared #1 ($2,400 rent), and I approved it on the dashboard: $3,400 → $1,000.
  * **Ticket 103:** the first attempt failed on a Portkey HTTP 500. Fixed by giving the model client 6 retries with backoff and a 120 s timeout in `backend/llm.py`, then retried from the dashboard (`run-194e1dae42af`): Boss → Inventory, Accounting, Customer Service. Inventory prepared #2 (22 hoodies, $484), and I approved it: $1,000 → $516.
  * **Retry noted:** my first Approve click on #1 sent no request, and the second worked.
  * **Cash check:** $3,400.00 + $0.00 − $2,884.00 = $516.00, which equals `cash_accounts`.
  * **Files:** filled the three Actual sections and the itemized Cash tab in `output/desk_tickets.html`, with the Expected sections byte-identical. Wrote `output/resolved_tickets.json` and `output/resolved_board.html` (4 embedded dashboard screenshots taken with Playwright). The audit trail grew to 1,329 records with earlier runs preserved. Finished `output/harness.md` with Dashboard and Final run sections.
  * **Verification:** all 10 final checks passed.

---

## Problem 10: Reflection tab

* **Prompt I typed:** Problem 10: Please take the Problem10_Reflection_vF.docx and add it to the reflection tab in the desk_tickets.html. Please format as you see fit and make it look nice.
* **Follow-up prompts:** None.
* **What was lacking after the first prompt:** Nothing. The prompt named my final reflection doc and the tab it goes in, and left the layout up to Claude.
* **Evidence I worked on the problem:**
  * **My reflection:** `Problem10_Reflection_vF.docx` (1,059 words) covers how the agents did on tickets 101–103, Actual vs. my Expected plan, one agent vs. five, and three problems the team could and couldn't solve.
  * **Reflection tab:** my text went into the Reflection tab of `output/desk_tickets.html` word for word (checked against the docx). Layout:
    * a card for each ticket, with the agents who worked it in the dashboard's colors, the cash change, and the problem paragraph highlighted
    * the Actual vs. Expected table
    * "one agent vs. five" side by side
    * idea cards for sections 4 and 5, marked "ideas, not run"
  * **Checks:**
    * Tickets 101–103, Cash, the page header, and the tab script are byte-identical to before.
    * Checked in Chrome at desktop width in light and dark mode and at phone width, with no page errors.
    * Fixed an older reflection style that had also changed the "not a hand-off" labels on the ticket tabs.

---
