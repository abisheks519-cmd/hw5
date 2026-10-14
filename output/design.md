# Campus Customs Agent Desk: dashboard design

The dashboard lives in `frontend/` (React + Vite + TypeScript). Start it from that folder with `npm run dev` (http://localhost:5173). It talks only to the real FastAPI backend at http://localhost:8000, so every ticket, event, transaction, and dollar on screen is live data.

The idea behind the whole design is a **shared desk**. Five agents work the tickets in the middle of the room, and you sit at the money drawer on the right. Nothing leaves the drawer unless you sign for it.

---

## Layout

The dashboard has three columns under a navy masthead, read left to right in the order you use them.

| Area | What's there | Why it's there |
| --- | --- | --- |
| **Masthead** | "Campus Customs · Agent Desk", the shop date (2026-08-31), a live backend light ("Backend live · team ready"), and **Reset database** | You always know which "day" the shop is on and whether the backend is up. Reset needs two clicks ("Click again to reset") so it can't be hit by accident. |
| **Left: Ticket queue** | Cards for #101, #102, #103 with a status pill, the requester, the type, and the item; a progress bar ("1 of 3 resolved") | It's the to-do list. It stays pinned while you scroll, so you can jump between tickets any time. |
| **Center: Ticket stage** | The selected ticket's subject and note, the big **Start the agent team** button, a five-avatar "crew" strip, and the **team map** | One clear action per ticket. The map shows the team before, during, and after the run. |
| **Center: Activity** | The live feed of what each agent said and did | It's the story of the run, in order, as it happens. |
| **Center: Who did what** | The Boss's wrap-up, then one card per agent | The short summary of each agent's contribution once the run is done. |
| **Right: Money desk** | The checking balance, **Waiting for your approval** cards, the cash log, and the approved history | Everything that can move money sits in one place, and it stays pinned so the balance is always in view. |

On narrower screens the money desk drops below the stage; on phones everything stacks in one column.

---

## How the agents look distinct

Each agent has three things that stay the same everywhere they appear: avatar, feed rows, hand-off tags, contribution cards, the team map, and the approval card's "prepared by" line.

| Agent | Color | Glyph | Role line |
| --- | --- | --- | --- |
| Boss | violet `#6250d6` | star | Runs the desk, routes the work |
| Inventory | green-teal `#12936a` | box | Stock, shortages, reorders |
| Accounting | blue `#2a78d6` | ledger | Cash, prices, payments |
| Facilities | orange `#e0602c` | building | Lease and landlord |
| Customer Service | pink `#cf4a7d` | speech bubble | Replies to customers |
| You (approvals) | gold `#9a6a00` | person | Approves money |

- **Color is never the only cue.** The name is always printed next to the avatar, each glyph is a different shape, and hovering an avatar shows the role.
- **Agent colors aren't status colors.** No agent uses the status green, amber, or red, so a "Resolved" pill is never mistaken for an agent.
- **The team map makes delegation visible.**
  - Faint dashed lines join every pair of agents, which shows the full connectivity: any agent can ask any other.
  - When an agent hands work off, a solid arrow in the asking agent's color appears from it to the helper. In the verified run of ticket 102, a violet arrow went Boss → Facilities and an orange one went Facilities → Accounting.
  - The newest arrow "marches" while the run is live.
  - The agent working right now has a pulsing ring.
  - Agents who haven't touched the ticket stay dim.
- **The crew strip** under the Start button fills in as agents join ("3 of 5 agents worked this ticket"), so you can see at a glance that the Boss only brought in the specialists it needed.
- **Activity feed rows** start with the agent's avatar and name in its color. Hand-offs and final answers get a left border and a light wash in that color. Each kind of step looks different:
  - Plain messages are speech bubbles.
  - Tool calls are monospace chips (`⚙ get_rent_due`) with their inputs.
  - Tool results fold away behind "returned data".
  - Refusals are red.
  - A hand-off reads like a route: *Boss → Facilities* plus the request.
  - Your approvals are gold bubbles.

  A "every step" toggle reveals the routine "decided to call…" steps for anyone who wants every detail.
- **Contribution cards** have a colored top edge for each agent. Each card shows:
  - who asked the agent, and how many times
  - its summary
  - the tools it used, with counts
  - who it handed off to
  - what it prepared
  - for Customer Service, its reply draft on lined "notepaper", labeled as a draft for a person to review and send

---

## How resolved tickets appear

A ticket's state shows in four places at once, so you can't miss it:

1. **Status pill** (card and stage). Each status pairs an icon with a word, never color alone:

   | Pill | Look |
   | --- | --- |
   | Open | amber ● |
   | Agents working | blue spinner |
   | Resolved | green ✓ |
   | Run failed | red ✕ |

2. **Ink stamp.** When a run finishes, the backend marks the ticket `resolved`. A double-bordered green **RESOLVED** stamp then lands on the ticket stage with a small "thunk" animation, like a rubber stamp on paper.
3. **Queue card.** It turns a soft green, and the progress bar at the top of the queue moves forward ("2 of 3 resolved").
4. **Start button.** It changes to "✓ Resolved by the team" and locks, so a finished ticket can't be run twice by mistake.

If the agents prepared a payment or a reorder, an amber nudge appears under the map: "1 transaction is waiting on the money desk. The agents prepared them, and only you can approve." Resolved means the team's work is done, but your decision is still waiting.

---

## How cash appears

- **Balance tile.** A deep green-to-navy tile shows the checking balance from `GET /api/cash` in a large figure ($3,400.00 after a reset).
  - Under the figure is a signed change ("▼ $2,400.00 approved since reset") and the "as of" date.
  - When the balance changes after an approval, the tile flashes with an amber glow, so the decrease is noticeable. In the verified run it went from $3,400.00 to $1,000.00.
- **Approval cards.** These are the biggest controls on the page. Each card shows:
  - the kind and number ("RENT · #1")
  - the amount in large type ($2,400.00)
  - the agent's one-line description
  - "prepared by Accounting for ticket 102", with Accounting's avatar
  - a preview of the result: "Checking after approval: $1,000.00", in red if it would drop under the shop's $500 warning line or below zero

  The full-width green **Approve $2,400.00** button names the exact amount, so you know what you're signing.
- **Cash log.** A small ledger lists the starting balance, each approved transaction (−$2,400.00 with the running balance under it), and a bold "Now" line. Starting − approvals = now, and you can add it up yourself.

---

## Loading, errors, and no double clicks

- **Loading.** Shimmering skeleton blocks stand in for tickets, feed rows, and the balance until the first response arrives. A "typing" indicator (three pulsing dots) sits at the bottom of the feed while agents are working.
- **Errors.**
  - If the backend is down, a red banner says so and shows the exact command to start it.
  - Each panel shows its own error inline instead of going blank.
  - Failed actions raise a red toast with the backend's message, for example a 409: "Not charged: Transaction 1 was already approved…".
- **Duplicate-proof actions.**
  - **Start.** It's disabled while the request is in flight and for the whole run. The backend also refuses a second run with 409.
  - **Approve.** It's disabled while its request is in flight, and disabled until you type your name in "Approving as". The backend flips the transaction from pending to approved inside one locked database transaction, so even two simultaneous clicks pay only once.
  - **Reset.** It needs a second click, and it's disabled during a run.
- **Live data.**
  - The board (tickets, transactions, balance) refreshes every 5 seconds.
  - During a run, the feed polls `GET /api/events?run_id=…&after=…` every 1.2 seconds, so only new events come over. It also polls `GET /api/runs/{id}` for status and contributions.
  - When the run ends, the board refreshes itself and a toast says "Ticket 102 is resolved. Check the money desk for anything to approve."

---

## Why these choices make it enjoyable to use

- **It reads like a story.** The feed is a conversation, not a log file: the Boss says what it's doing, hands off with a visible arrow, and the helper reports back. You can follow it the way you'd follow a group chat, and the "every step" toggle is there when you want the raw detail.
- **You can feel who's working.** The pulsing avatar, the marching arrow, and the crew strip lighting up make the agents feel like teammates. It's satisfying to watch the Boss pull in only Facilities and Accounting for a rent notice and leave the others alone.
- **Finishing feels finished.** The rubber stamp, the green card, and the moving progress bar are small rewards that make clearing the queue fun, and they leave no doubt about what's done.
- **Money feels serious, in a good way.** The approval cards are the loudest thing on the page, name the exact amount on the button, and preview the balance before you click. The tile visibly flashes and drops after you approve, and the ledger lets you check the math. You stay in control without reading JSON.
- **It's warm, not clinical.** The paper-desk background, the rounded cards, the friendly display font for headings, and the plain-English labels make it feel like a small shop's back office, not an admin console. It also works in dark mode, and it respects the "reduce motion" setting by turning the animations off.

## Files

| File | What it does |
| --- | --- |
| `frontend/src/App.tsx` | Page layout, live polling, starting runs, approvals, reset, toasts |
| `frontend/src/api.ts` | Typed client for every backend route (`http://localhost:8000`, or `VITE_API_BASE`) |
| `frontend/src/agents.tsx` | Agent identities (color, glyph, role) and the `Avatar` and `AgentTag` components |
| `frontend/src/components/TicketList.tsx` | Ticket queue and status pills |
| `frontend/src/components/TeamMap.tsx` | The delegation map |
| `frontend/src/components/ActivityFeed.tsx` | The live activity feed |
| `frontend/src/components/Contributions.tsx` | "Who did what" cards and the Boss's wrap-up |
| `frontend/src/components/MoneyDesk.tsx` | Balance tile, approval cards, cash log |
| `frontend/src/styles.css` | The visual design: light and dark, reduced motion |
