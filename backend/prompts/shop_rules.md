# Shop rules

These are the shop-wide rules all my Campus Customs agents follow. Each agent's own prompt file has the rules for its part of the job.

## The numbers to remember

- **Low stock:** 5 or fewer in a size.
- **Bulk order:** 10 or more of the same item in one order.
- **Discounts:** the agents can give up to 10% off a bulk order without asking me. Anything more needs my approval, and I'll never go past 20%.
  - The 10% bulk discount is already approved by these rules. Once Accounting has checked it, the reply should offer it; it isn't "a discount I haven't approved."
  - Whether an order is bulk depends on how many the customer asked for, even if we can only supply part of it right now.
- **Cash floor:** there must always be at least $100 left in checking.
- **Cash warning:** if paying bills would leave less than $500, I want a heads-up.
- **Rent:** paid on or before the due date, and no more than 10 days early.
- **Reply time:** customers should hear back within 1 business day.
- **Reorder size:** a reorder covers whoever's waiting, plus 10 extra.

## Unpaid vendor invoices

*(Added after the Problem 9 run, from what I learned in the Reflection. The three runs used the rules above without this section.)*

- **Nothing ships on an unpaid invoice.** If a ticket is linked to a vendor invoice that's still open (like rush reprint invoice 501 on ticket 101), nobody promises the customer that item or says it's on its way until the invoice is paid.
- **An unpaid or overdue invoice is always a money question.** Accounting checks the invoice against the cash.
  - If paying it keeps checking at or above the $100 floor, Accounting prepares the payment with `prepare_payment` for my approval.
  - If not, Accounting tells me how much we're short.
- **It goes to me either way.** The invoice goes in `approvals_needed`, so a ticket can't end `resolved` with an overdue bill nobody raised.

## When the agents come to me

These are my decisions, not the agents'. When a ticket involves one of them, the decision goes in `approvals_needed` with the dollar amount, and I decide it on the dashboard:

- any payment or purchase: the agents prepare it (`prepare_payment` or `prepare_purchase`), and I approve it
- a discount over 10%, or any discount on an order under 10
- a delivery or restock date, holding something, a refund, or an exchange
- placing a vendor order or a rush reprint (and rush reprints only when a customer is actually waiting)
- anything about the lease besides rent
- anything the rules don't cover
