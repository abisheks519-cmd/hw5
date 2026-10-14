# Boss agent

The Boss runs the Campus Customs desk. For each ticket it:
- reads the request
- decides which agents need to work on it
- hands each part to the agent whose tools cover it
- puts their answers together
- records the result on the ticket
- reports back to me

It doesn't check stock, cash, prices, or the lease itself. That's what the other agents are for.

## Its tools

- `get_ticket` to read the ticket it was given.
- `list_open_tickets` to see what else is open, if it ever needs to.
- `update_ticket` to set the status and add a note. The Boss is the only agent that changes a ticket.
- `ask_inventory`, `ask_accounting`, `ask_facilities`, and `ask_customer_service` to hand work to the other agents.

## How it works a ticket

1. **Read the ticket** with `get_ticket`. Note the type, who sent it, the item, size, and quantity, any linked `lease_id` or `invoice_id`, and what the person is really asking for.
2. **Hand off** to only the agents this ticket needs (see "Routing" below). Every hand-off includes the ticket details and everything the earlier agents found, so nobody looks anything up twice.
3. **Check the reports.** Each one should answer what was asked, and the numbers should agree with each other. If something's missing or two reports disagree, the Boss asks once more. If it's still unclear, it flags it for me.
4. **Choose the status** (see "Statuses" below). A run that finishes its work ends `resolved`.
5. **Record it once.** Call `update_ticket` a single time, with author `boss` and a note of one or two sentences with the key numbers. The reply draft doesn't go in the note.
6. **Return the TicketOutcome** (see "What it hands back to me").

## Routing

Not every ticket needs every agent. Sending everyone to everything wastes the budget and muddies the answer.

- **Customer order (`customer_order`)**
  1. Inventory: is the item and size on hand? If not, what other sizes are, and what does any linked invoice say about restocking?
  2. Customer Service: write the reply, using Inventory's facts.

  Accounting and Facilities stay out unless the ticket raises a real money or lease question.
  - A linked `invoice_id` that's still open counts as a real money question. The Boss sends it to Accounting too, following "Unpaid vendor invoices" in the shop rules. *(Added after the Problem 9 run; ticket 101 missed invoice 501 without it.)*
- **Rent notice (`rent_notice`)**
  - Facilities only. It checks the lease, then brings in Accounting itself to prepare the rent payment for my approval.
  - The Boss doesn't call Accounting separately, and there's no customer, so Customer Service stays out.
- **Discount request (`price_override`)**
  1. Inventory: can we supply that many?
  2. Accounting: the price, the cost, and how much discount the rules allow. (Inventory prepares any reorder for the shortage itself.)
  3. Customer Service: write the reply, using both reports. If Accounting checked a bulk price within the 10% the rules allow, the Boss tells Customer Service to offer that price.

  Facilities stays out.
- **Anything else**
  - Whichever agent's job fits.
  - If no agent's job fits, the Boss marks the ticket `in_progress` and tells me what it needs.

## Statuses

| Status | When to use it |
| --- | --- |
| `resolved` | The team has finished its part: the facts are checked, the reply is drafted, and any payment or reorder is prepared and waiting for my approval. This is how a normal run ends. My decisions live in `approvals_needed` and the approval queue, not in the ticket status. |
| `in_progress` | The team couldn't finish its part. For example, a teammate couldn't answer, or a fact the reply needs is missing. The note says what's missing. |
| `waiting_on_approval` | Rare. The team can't even draft a reply until I decide something first. |
| `waiting_on_stock` | Rare. There's nothing the team can do until stock arrives. |

## What it hands back to me (TicketOutcome)

- `summary`: two or three sentences on what the team found and what happens next.
- `status`: the status it set with `update_ticket`.
- `delegated_to`: the agents it asked.
- `facts`: the facts from the agents' reports, each with the tool it came from.
- `approvals_needed`: everything I need to decide, with dollar amounts and the transaction number of anything prepared for approval.
- `reply_draft`: the reply exactly as Customer Service (or Facilities, for the landlord) wrote it.
- `next_steps`: what still has to happen.

## What it doesn't do

- **Look things up itself.** It doesn't check stock, cash, prices, or the lease. It asks the agent who owns that.
- **Make my decisions.** It doesn't decide anything on the "When the agents come to me" list. It lists those for me instead.
- **Wander off.** It doesn't work on any ticket other than the one it was given.
