"""Campus Customs MCP server.

Every Campus Customs agent gets its data through the tools in this file. Each tool reads
(or, for the write tools, updates) data/campus_customs_new.db and returns only what is stored
there, plus simple arithmetic on those values (margins, totals, days until a due date). No tool
invents a record. Agents can never move money: they only prepare payments and purchases, and a
person approves them through approve_transaction.

Run it (stdio transport):  .venv/bin/python mcp_server/server.py

Environment (both optional):
  CC_DB_PATH           database file to use instead of data/campus_customs_new.db
                       (tests point this at a throwaway copy)
  CC_HUMAN_APPROVALS   "1" adds the approve_transaction tool. Only the FastAPI backend sets it, on its
                       own connection; the agents' connection and Claude Code never get the tool.
"""

import calendar
import os
import re
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

HW_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("CC_DB_PATH") or HW_DIR / "data" / "campus_customs_new.db")
if not DB_PATH.is_absolute():
    DB_PATH = HW_DIR / DB_PATH
HUMAN_APPROVALS = os.environ.get("CC_HUMAN_APPROVALS") == "1"
RENT_EARLY_DAYS = 10  # rent can be prepared/paid at most this many days before it is due
NOTE_MAX_CHARS = 600

mcp = FastMCP(
    name="campus-customs",
    instructions=(
        "Back-office tools for the Campus Customs shop. Every value comes from "
        "data/campus_customs_new.db. Use these tools instead of guessing stock, rent, cash, or prices. "
        "If a tool says a record does not exist, report that instead of inventing one. "
        "Agents never move money: prepare_payment and prepare_purchase only queue a transaction, and a person approves it."
    ),
)

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}
MONEY = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False}

TicketStatus = Literal["open", "in_progress", "waiting_on_stock", "waiting_on_approval", "resolved"]
AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
TicketAuthor = Literal["boss", "inventory", "accounting", "facilities", "customer_service", "dashboard"]


def connect() -> sqlite3.Connection:
    """Open the database read-only, so a lookup can never change it."""
    if not DB_PATH.exists():
        raise ToolError(f"Database not found at {DB_PATH}.")
    con = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def connect_rw() -> sqlite3.Connection:
    """Open the existing database for writing (mode=rw never creates a new file)."""
    if not DB_PATH.exists():
        raise ToolError(f"Database not found at {DB_PATH}.")
    con = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=rw", uri=True, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def shop_date(con: sqlite3.Connection) -> str | None:
    row = con.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return row["date_today"] if row else None


def days_between(start: str | None, end: str) -> int | None:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days if start else None


def ids_on_file(con: sqlite3.Connection, table: str) -> str:
    return ", ".join(str(r[0]) for r in con.execute(f"SELECT id FROM {table} ORDER BY id")) or "none"


def scrub(text: str) -> str:
    """Remove personal details (emails, phone numbers, card numbers) before text is stored."""
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email removed]", text)
    text = re.sub(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{1,7}\b", "[card number removed]", text)
    return re.sub(r"(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b", "[phone removed]", text)


# ---------------------------------------------------------------- check_inventory

class SizeStock(BaseModel):
    size: str = Field(description="Size code: S, M, L, XL, or OS (one size)")
    qty: int = Field(description="Units on hand (inventory.qty)")
    location: str = Field(description="Where it is shelved (inventory.location)")
    in_stock: bool = Field(description="True when qty is above 0")


class InventoryCheck(BaseModel):
    sku: str
    name: str = Field(description="Product name (inventory.name)")
    sizes: list[SizeStock]
    total_qty: int = Field(description="Sum of qty across the sizes returned")


@mcp.tool(annotations=READ_ONLY)
def check_inventory(
    sku: Annotated[str, Field(description="Product code, e.g. CC-TEE-WHITE")],
    size: Annotated[str | None, Field(description="One size (S, M, L, XL, OS). Leave out to get every size.")] = None,
) -> InventoryCheck:
    """Units on hand and shelf location for a product, per size, from the inventory table.

    Use before promising a customer an item or quoting how many units the shop can supply.
    """
    sku = sku.strip().upper()
    size = size.strip().upper() if size else None
    with closing(connect()) as con:
        rows = con.execute(
            "SELECT name, size, qty, location FROM inventory WHERE sku = ? ORDER BY rowid", (sku,)
        ).fetchall()
        if not rows:
            known = [r[0] for r in con.execute("SELECT DISTINCT sku FROM inventory ORDER BY sku")]
            raise ToolError(f"No inventory for SKU {sku!r}. SKUs in inventory: {', '.join(known)}.")
    picked = [r for r in rows if size is None or r["size"] == size]
    if not picked:
        raise ToolError(f"{sku} has no size {size!r}. Sizes on file: {', '.join(r['size'] for r in rows)}.")
    return InventoryCheck(
        sku=sku,
        name=rows[0]["name"],
        sizes=[SizeStock(size=r["size"], qty=r["qty"], location=r["location"], in_stock=r["qty"] > 0) for r in picked],
        total_qty=sum(r["qty"] for r in picked),
    )


# ---------------------------------------------------------------- get_rent_due

class RentDue(BaseModel):
    lease_id: int
    space_name: str = Field(description="The rented space (leases.space_name)")
    landlord: str = Field(description="Who the rent is paid to (leases.landlord)")
    monthly_rent: float = Field(description="Rent per month in dollars (leases.monthly_rent)")
    next_due: str = Field(description="Next rent due date, YYYY-MM-DD (leases.next_due)")
    notes: str | None = Field(description="Lease notes (leases.notes)")
    shop_date: str | None = Field(description="The shop's current date (desk.date_today)")
    days_until_due: int | None = Field(description="next_due minus shop_date in days; negative means overdue")


@mcp.tool(annotations=READ_ONLY)
def get_rent_due(
    lease_id: Annotated[int, Field(description="Lease id, e.g. the lease_id on a rent_notice ticket")],
) -> RentDue:
    """Rent amount, landlord, and next due date for a lease, from the leases table.

    Counts the days until rent is due from the shop's date in the desk table, not the real clock.
    """
    with closing(connect()) as con:
        lease = con.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if lease is None:
            raise ToolError(f"No lease with id {lease_id}. Lease ids on file: {ids_on_file(con, 'leases')}.")
        today = shop_date(con)
    return RentDue(
        lease_id=lease["id"],
        space_name=lease["space_name"],
        landlord=lease["landlord"],
        monthly_rent=lease["monthly_rent"],
        next_due=lease["next_due"],
        notes=lease["notes"],
        shop_date=today,
        days_until_due=days_between(today, lease["next_due"]),
    )


# ---------------------------------------------------------------- get_pricing

class Pricing(BaseModel):
    sku: str
    unit_cost: float = Field(description="What the shop pays per unit (pricing.unit_cost)")
    list_price: float = Field(description="Normal selling price per unit (pricing.list_price)")
    margin_per_unit: float = Field(description="list_price minus unit_cost: the most a discount can take off one unit before selling at a loss")
    margin_pct: float = Field(description="margin_per_unit as a percent of list_price")
    quantity: int = Field(description="Units the totals below are for")
    list_total: float = Field(description="quantity × list_price")
    cost_total: float = Field(description="quantity × unit_cost")


def pricing_row(con: sqlite3.Connection, sku: str) -> sqlite3.Row:
    row = con.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
    if row is None:
        known = [r[0] for r in con.execute("SELECT sku FROM pricing ORDER BY sku")]
        raise ToolError(f"No pricing for SKU {sku!r}. SKUs with pricing: {', '.join(known)}.")
    return row


@mcp.tool(annotations=READ_ONLY)
def get_pricing(
    sku: Annotated[str, Field(description="Product code, e.g. CC-HOOD-NAVY")],
    quantity: Annotated[int, Field(ge=1, description="Units being priced, e.g. a bulk order size")] = 1,
) -> Pricing:
    """Unit cost, list price, and margin for a product, from the pricing table.

    Use before quoting a price or deciding on a discount, so no offer goes below cost.
    """
    sku = sku.strip().upper()
    with closing(connect()) as con:
        row = pricing_row(con, sku)
    cost, price = row["unit_cost"], row["list_price"]
    return Pricing(
        sku=sku,
        unit_cost=cost,
        list_price=price,
        margin_per_unit=round(price - cost, 2),
        margin_pct=round((price - cost) / price * 100, 1),
        quantity=quantity,
        list_total=round(price * quantity, 2),
        cost_total=round(cost * quantity, 2),
    )


# ---------------------------------------------------------------- check_discount

class DiscountCheck(BaseModel):
    sku: str
    quantity: int
    discount_pct: float = Field(description="Discount being tested, percent off list_price")
    list_price: float = Field(description="pricing.list_price")
    unit_cost: float = Field(description="pricing.unit_cost")
    discounted_unit_price: float = Field(description="list_price × (1 − discount_pct/100)")
    discounted_total: float = Field(description="quantity × discounted_unit_price")
    customer_saves: float = Field(description="quantity × list_price − discounted_total")
    margin_per_unit_after: float = Field(description="discounted_unit_price − unit_cost")
    margin_total_after: float = Field(description="quantity × margin_per_unit_after")
    below_cost: bool = Field(description="True if the discounted price is below unit_cost (the shop would lose money)")


@mcp.tool(annotations=READ_ONLY)
def check_discount(
    sku: Annotated[str, Field(description="Product code, e.g. CC-HOOD-NAVY")],
    quantity: Annotated[int, Field(ge=1, description="Units in the order")],
    discount_pct: Annotated[float, Field(ge=0, lt=100, description="Percent off list price to test, e.g. 10 for 10%")],
) -> DiscountCheck:
    """Test a proposed discount against the pricing table: new price, totals, and margin left.

    Says whether the discounted price would fall below the shop's unit cost. It only calculates;
    it does not approve or apply the discount.
    """
    sku = sku.strip().upper()
    with closing(connect()) as con:
        row = pricing_row(con, sku)
    cost, price = row["unit_cost"], row["list_price"]
    unit = round(price * (1 - discount_pct / 100), 2)
    return DiscountCheck(
        sku=sku,
        quantity=quantity,
        discount_pct=discount_pct,
        list_price=price,
        unit_cost=cost,
        discounted_unit_price=unit,
        discounted_total=round(unit * quantity, 2),
        customer_saves=round((price - unit) * quantity, 2),
        margin_per_unit_after=round(unit - cost, 2),
        margin_total_after=round((unit - cost) * quantity, 2),
        below_cost=unit < cost,
    )


# ---------------------------------------------------------------- tickets

class Ticket(BaseModel):
    id: int
    type: str = Field(description="customer_order, rent_notice, price_override, ...")
    requester: str
    subject: str
    sku: str | None
    size: str | None
    qty: int | None
    lease_id: int | None = Field(description="Linked lease (leases.id), if any")
    invoice_id: int | None = Field(description="Linked vendor invoice (invoices.id), if any")
    status: str
    notes: str | None = Field(description="The original request, then one line per update_ticket call")
    created_at: str


class OpenTickets(BaseModel):
    shop_date: str | None = Field(description="The shop's current date (desk.date_today)")
    tickets: list[Ticket] = Field(description="Every ticket whose status is not 'resolved', oldest first")


def ticket_row(con: sqlite3.Connection, ticket_id: int) -> Ticket:
    row = con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise ToolError(f"No ticket with id {ticket_id}. Ticket ids on file: {ids_on_file(con, 'tickets')}.")
    return Ticket(**dict(row))


@mcp.tool(annotations=READ_ONLY)
def list_open_tickets() -> OpenTickets:
    """Every ticket that is not resolved yet, from the tickets table, plus the shop's date."""
    with closing(connect()) as con:
        rows = con.execute("SELECT * FROM tickets WHERE status != 'resolved' ORDER BY id").fetchall()
        return OpenTickets(shop_date=shop_date(con), tickets=[Ticket(**dict(r)) for r in rows])


@mcp.tool(annotations=READ_ONLY)
def get_ticket(
    ticket_id: Annotated[int, Field(description="Ticket id, e.g. 101")],
) -> Ticket:
    """One ticket from the tickets table: who asked, what for, linked SKU/lease/invoice, status, and notes."""
    with closing(connect()) as con:
        return ticket_row(con, ticket_id)


@mcp.tool(annotations=WRITE)
def update_ticket(
    ticket_id: Annotated[int, Field(description="Ticket id, e.g. 101")],
    status: Annotated[TicketStatus, Field(description="New status for the ticket")],
    note: Annotated[str, Field(min_length=1, max_length=NOTE_MAX_CHARS, description="What was found or decided, in one or two sentences")],
    author: Annotated[TicketAuthor, Field(description="Agent making the update ('dashboard' when the backend closes a finished run)")],
) -> Ticket:
    """Set a ticket's status and append a dated, signed note to tickets.notes.

    Earlier notes are kept. Emails, phone numbers, and card numbers are removed from the note
    before it is saved. This records work inside the shop; it does not contact the customer.
    """
    with closing(connect_rw()) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            ticket = ticket_row(con, ticket_id)
            line = f"[{shop_date(con)} {author}: {ticket.status} -> {status}] {scrub(note.strip())}"
            notes = f"{ticket.notes}\n{line}" if ticket.notes else line
            con.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
            updated = ticket_row(con, ticket_id)
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
    return updated


# ---------------------------------------------------------------- invoices, vendors, cash

class InvoiceDetail(BaseModel):
    id: int
    vendor_id: int
    vendor_name: str = Field(description="vendors.name")
    vendor_specialty: str = Field(description="vendors.specialty")
    vendor_lead_days: int = Field(description="vendors.lead_days: days from order to delivery")
    amount: float = Field(description="Amount owed in dollars (invoices.amount)")
    due_date: str
    status: str = Field(description="open or paid")
    description: str | None
    shop_date: str | None = Field(description="The shop's current date (desk.date_today)")
    days_until_due: int | None = Field(description="due_date minus shop_date; negative means overdue")


@mcp.tool(annotations=READ_ONLY)
def get_invoice(
    invoice_id: Annotated[int, Field(description="Invoice id, e.g. the invoice_id on a ticket")],
) -> InvoiceDetail:
    """A vendor invoice from the invoices table with its vendor's name and lead time from vendors."""
    with closing(connect()) as con:
        row = con.execute(
            "SELECT i.*, v.name AS vendor_name, v.specialty AS vendor_specialty, v.lead_days AS vendor_lead_days "
            "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?", (invoice_id,)
        ).fetchone()
        if row is None:
            raise ToolError(f"No invoice with id {invoice_id}. Invoice ids on file: {ids_on_file(con, 'invoices')}.")
        today = shop_date(con)
    return InvoiceDetail(**dict(row), shop_date=today, days_until_due=days_between(today, row["due_date"]))


class Vendor(BaseModel):
    id: int
    name: str
    specialty: str = Field(description="What they supply")
    lead_days: int = Field(description="Days from order to delivery")


class VendorList(BaseModel):
    vendors: list[Vendor]


@mcp.tool(annotations=READ_ONLY)
def list_vendors() -> VendorList:
    """Every vendor from the vendors table: what they supply and how many days delivery takes."""
    with closing(connect()) as con:
        return VendorList(vendors=[Vendor(**dict(r)) for r in con.execute("SELECT * FROM vendors ORDER BY id")])


class CashAccount(BaseModel):
    name: str
    balance: float
    as_of: str = Field(description="cash_accounts.date")


class OpenBill(BaseModel):
    invoice_id: int
    vendor_name: str
    amount: float
    due_date: str
    days_until_due: int | None = Field(description="Negative means overdue")
    description: str | None


class RentBill(BaseModel):
    lease_id: int
    space_name: str
    landlord: str
    monthly_rent: float
    next_due: str
    days_until_due: int | None


class CashPosition(BaseModel):
    shop_date: str | None
    accounts: list[CashAccount]
    cash_total: float = Field(description="Sum of cash_accounts.balance")
    open_invoices: list[OpenBill] = Field(description="Invoices with status 'open'")
    open_invoices_total: float
    rent_due: list[RentBill] = Field(description="Leases whose next rent is due within 31 days of shop_date (or overdue)")
    rent_due_total: float
    cash_after_paying_all: float = Field(description="cash_total − open_invoices_total − rent_due_total")


@mcp.tool(annotations=READ_ONLY)
def get_cash_position() -> CashPosition:
    """Cash on hand (cash_accounts) next to what the shop owes: open invoices and rent due within a month.

    Use before deciding whether and in what order bills can be paid.
    """
    with closing(connect()) as con:
        today = shop_date(con)
        accounts = [CashAccount(name=r["name"], balance=r["balance"], as_of=r["date"])
                    for r in con.execute("SELECT * FROM cash_accounts ORDER BY name")]
        bills = [OpenBill(invoice_id=r["id"], vendor_name=r["vendor_name"], amount=r["amount"], due_date=r["due_date"],
                          days_until_due=days_between(today, r["due_date"]), description=r["description"])
                 for r in con.execute("SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
                                      "WHERE i.status = 'open' ORDER BY i.due_date")]
        rent = [RentBill(lease_id=r["id"], space_name=r["space_name"], landlord=r["landlord"], monthly_rent=r["monthly_rent"],
                         next_due=r["next_due"], days_until_due=days_between(today, r["next_due"]))
                for r in con.execute("SELECT * FROM leases ORDER BY next_due")]
    rent = [r for r in rent if r.days_until_due is None or r.days_until_due <= 31]
    cash, owed, rent_total = (round(sum(x), 2) for x in ([a.balance for a in accounts], [b.amount for b in bills], [r.monthly_rent for r in rent]))
    return CashPosition(shop_date=today, accounts=accounts, cash_total=cash, open_invoices=bills, open_invoices_total=owed,
                        rent_due=rent, rent_due_total=rent_total, cash_after_paying_all=round(cash - owed - rent_total, 2))


def add_month(d: str) -> str:
    y, m, day = (int(x) for x in d.split("-"))
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return date(y, m, min(day, calendar.monthrange(y, m)[1])).isoformat()


# ---------------------------------------------------------------- all tickets

class AllTickets(BaseModel):
    shop_date: str | None = Field(description="The shop's current date (desk.date_today)")
    tickets: list[Ticket] = Field(description="Every ticket, open or resolved, oldest first")


@mcp.tool(annotations=READ_ONLY)
def list_tickets() -> AllTickets:
    """Every ticket in the tickets table, open or resolved, plus the shop's date."""
    with closing(connect()) as con:
        rows = con.execute("SELECT * FROM tickets ORDER BY id").fetchall()
        return AllTickets(shop_date=shop_date(con), tickets=[Ticket(**dict(r)) for r in rows])


# ---------------------------------------------------------------- prepared transactions
#
# Agents never move money. They PREPARE a payment (a vendor invoice or rent) or a purchase
# (a vendor reorder), which only adds a row to pending_transactions. Cash changes only when a
# person approves it: approve_transaction, which exists only on a server started with
# CC_HUMAN_APPROVALS=1 (the FastAPI backend's own connection), never on the agents' connection.

PENDING_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_transactions (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('invoice', 'rent', 'purchase')),
    ref_id      INTEGER,          -- invoices.id or leases.id; NULL for a purchase
    ref_due     TEXT,             -- the bill's due date when it was prepared
    sku         TEXT,             -- purchase only
    size        TEXT,             -- purchase only
    qty         INTEGER,          -- purchase only
    vendor_id   INTEGER,          -- purchase only (vendors.id)
    amount      REAL NOT NULL,
    description TEXT NOT NULL,
    ticket_id   INTEGER,
    prepared_by TEXT NOT NULL,
    prepared_at TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved')),
    approved_by TEXT,
    approved_at TEXT,
    payment_id  INTEGER           -- payments.id once approved
);
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_per_bill
    ON pending_transactions (kind, ref_id) WHERE status = 'pending' AND kind != 'purchase';
"""


class PreparedTransaction(BaseModel):
    id: int = Field(description="pending_transactions.id; a person approves it by this id")
    kind: Literal["invoice", "rent", "purchase"]
    ref_id: int | None = Field(description="invoices.id or leases.id; empty for a purchase")
    ref_due: str | None = Field(description="Due date of the bill when it was prepared")
    sku: str | None
    size: str | None
    qty: int | None
    vendor_id: int | None
    amount: float
    description: str
    ticket_id: int | None
    prepared_by: str
    prepared_at: str
    status: Literal["pending", "approved"]
    approved_by: str | None
    approved_at: str | None
    payment_id: int | None


class PrepareResult(BaseModel):
    transaction: PreparedTransaction
    already_prepared: bool = Field(description="True if this exact transaction was already waiting; nothing new was added")
    checking_balance: float = Field(description="cash_accounts balance for checking right now")
    balance_if_approved: float = Field(description="checking balance after this transaction, if a person approves it")
    next_step: str


class TransactionList(BaseModel):
    transactions: list[PreparedTransaction]
    pending_total: float = Field(description="Sum of the amounts still waiting for approval")


def ensure_pending_table(con: sqlite3.Connection) -> None:
    con.executescript(PENDING_SCHEMA)


def pending_table_exists(con: sqlite3.Connection) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pending_transactions'").fetchone() is not None


def transaction_row(con: sqlite3.Connection, transaction_id: int) -> PreparedTransaction | None:
    row = con.execute("SELECT * FROM pending_transactions WHERE id = ?", (transaction_id,)).fetchone()
    return PreparedTransaction(**dict(row)) if row else None


def checking_balance(con: sqlite3.Connection) -> float:
    row = con.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()
    if row is None:
        raise ToolError("There is no checking account in cash_accounts.")
    return row["balance"]


def save_prepared(con: sqlite3.Connection, existing: sqlite3.Row | None, values: dict) -> PrepareResult:
    """Insert a pending transaction (or return the one already waiting) and commit."""
    if existing is None:
        cols = ", ".join(values)
        cur = con.execute(f"INSERT INTO pending_transactions ({cols}) VALUES ({', '.join('?' * len(values))})", tuple(values.values()))
        txn_id = cur.lastrowid
    else:
        txn_id = existing["id"]
    txn = transaction_row(con, txn_id)
    balance = checking_balance(con)
    con.execute("COMMIT")
    return PrepareResult(
        transaction=txn, already_prepared=existing is not None, checking_balance=balance,
        balance_if_approved=round(balance - txn.amount, 2),
        next_step=f"Waiting for a person to approve transaction {txn.id} on the dashboard. No money has moved.",
    )


@mcp.tool(annotations=WRITE)
def prepare_payment(
    kind: Annotated[Literal["invoice", "rent"], Field(description="'invoice' for a vendor invoice, 'rent' for a lease")],
    ref_id: Annotated[int, Field(description="invoices.id for kind='invoice', leases.id for kind='rent'")],
    prepared_by: Annotated[AgentName, Field(description="Agent preparing it (normally accounting)")],
    ticket_id: Annotated[int | None, Field(description="Ticket this payment is for, if any")] = None,
) -> PrepareResult:
    """Prepare a payment for a person to approve. It does NOT move money.

    The amount is taken from the bill itself (the invoice amount, or the monthly rent), so it is always
    exact. It refuses an invoice that is already paid and rent more than 10 days before it is due. If the
    same bill is already waiting for approval, it returns that one instead of adding a duplicate.
    """
    with closing(connect_rw()) as con:
        ensure_pending_table(con)
        con.execute("BEGIN IMMEDIATE")
        try:
            today = shop_date(con) or date.today().isoformat()
            if kind == "invoice":
                bill = con.execute("SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
                                   "WHERE i.id = ?", (ref_id,)).fetchone()
                if bill is None:
                    raise ToolError(f"No invoice with id {ref_id}. Invoice ids on file: {ids_on_file(con, 'invoices')}.")
                if bill["status"] != "open":
                    raise ToolError(f"Invoice {ref_id} is already {bill['status']}; there is nothing to pay.")
                amount, due = bill["amount"], bill["due_date"]
                desc = f"Pay invoice {ref_id} to {bill['vendor_name']} (${amount:,.2f}): {bill['description'] or 'vendor invoice'}"
            else:
                lease = con.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
                if lease is None:
                    raise ToolError(f"No lease with id {ref_id}. Lease ids on file: {ids_on_file(con, 'leases')}.")
                if days_between(today, lease["next_due"]) > RENT_EARLY_DAYS:
                    raise ToolError(f"Rent for lease {ref_id} is next due {lease['next_due']}, more than {RENT_EARLY_DAYS} days "
                                    f"after the shop date {today}; it is not due yet (or was already paid).")
                amount, due = lease["monthly_rent"], lease["next_due"]
                desc = f"Pay rent for lease {ref_id} ({lease['space_name']}) to {lease['landlord']} (${amount:,.2f}), due {due}"
            existing = con.execute("SELECT id FROM pending_transactions WHERE kind = ? AND ref_id = ? AND status = 'pending'",
                                   (kind, ref_id)).fetchone()
            return save_prepared(con, existing, {
                "kind": kind, "ref_id": ref_id, "ref_due": due, "amount": amount, "description": desc,
                "ticket_id": ticket_id, "prepared_by": prepared_by, "prepared_at": today})
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise


@mcp.tool(annotations=WRITE)
def prepare_purchase(
    sku: Annotated[str, Field(description="Product code to reorder, e.g. CC-HOOD-NAVY")],
    size: Annotated[str, Field(description="Size to reorder, e.g. M")],
    qty: Annotated[int, Field(ge=1, le=500, description="Units to reorder")],
    vendor_id: Annotated[int, Field(description="vendors.id to buy from (see list_vendors)")],
    prepared_by: Annotated[AgentName, Field(description="Agent preparing it (normally inventory)")],
    ticket_id: Annotated[int | None, Field(description="Ticket this reorder is for, if any")] = None,
) -> PrepareResult:
    """Prepare a vendor reorder for a person to approve. It does NOT move money or change stock.

    The cost is qty × the product's unit_cost from the pricing table. If the same reorder (item, size,
    ticket) is already waiting for approval, it returns that one instead of adding a duplicate.
    """
    sku, size = sku.strip().upper(), size.strip().upper()
    with closing(connect_rw()) as con:
        ensure_pending_table(con)
        con.execute("BEGIN IMMEDIATE")
        try:
            today = shop_date(con) or date.today().isoformat()
            item = con.execute("SELECT name FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
            if item is None:
                raise ToolError(f"No inventory row for {sku} size {size}; only items the shop already stocks can be reordered.")
            cost = pricing_row(con, sku)["unit_cost"]
            vendor = con.execute("SELECT name FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
            if vendor is None:
                raise ToolError(f"No vendor with id {vendor_id}. Vendor ids on file: {ids_on_file(con, 'vendors')}.")
            amount = round(qty * cost, 2)
            existing = con.execute("SELECT id FROM pending_transactions WHERE kind = 'purchase' AND sku = ? AND size = ? "
                                   "AND ticket_id IS ? AND status = 'pending'", (sku, size, ticket_id)).fetchone()
            return save_prepared(con, existing, {
                "kind": "purchase", "sku": sku, "size": size, "qty": qty, "vendor_id": vendor_id, "amount": amount,
                "description": f"Reorder {qty} x {item['name']} ({sku}, size {size}) from {vendor['name']} at ${cost:,.2f} each (${amount:,.2f})",
                "ticket_id": ticket_id, "prepared_by": prepared_by, "prepared_at": today})
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise


@mcp.tool(annotations=READ_ONLY)
def list_pending_transactions(
    status: Annotated[Literal["pending", "approved", "all"], Field(description="Which transactions to list")] = "pending",
) -> TransactionList:
    """Prepared payments and purchases from pending_transactions, newest first."""
    with closing(connect()) as con:
        if not pending_table_exists(con):
            return TransactionList(transactions=[], pending_total=0)
        where = "" if status == "all" else "WHERE status = ?"
        rows = con.execute(f"SELECT * FROM pending_transactions {where} ORDER BY id DESC", () if status == "all" else (status,)).fetchall()
        txns = [PreparedTransaction(**dict(r)) for r in rows]
    return TransactionList(transactions=txns, pending_total=round(sum(t.amount for t in txns if t.status == "pending"), 2))


class ApprovalReceipt(BaseModel):
    transaction: PreparedTransaction
    payment_id: int = Field(description="New payments.id")
    amount: float
    balance_before: float
    balance_after: float
    effect: str = Field(description="What else changed: invoice marked paid, lease next_due moved, or reorder paid")
    warning: str | None = Field(description="Set when the balance after is under the shop's $500 warning line")


def approve_transaction(
    transaction_id: Annotated[int, Field(description="pending_transactions.id to approve")],
    approved_by: Annotated[str, Field(min_length=1, max_length=80, description="Name of the person approving it")],
) -> ApprovalReceipt:
    """Approve a prepared payment or purchase and move the money. Only for a person, never an agent.

    Runs as one database transaction: it re-checks the bill, refuses anything already approved (so a
    double click can never pay twice), refuses a payment larger than the checking balance, then adds
    the payments row, takes the money out of checking, marks the invoice paid or moves the lease's
    next_due forward (purchases only pay the vendor; stock arrives later), and notes it on the ticket.
    Error messages start with a code: not_found, already_approved, conflict, insufficient_funds, invalid.
    """
    who = approved_by.strip()
    if not who or who.casefold() in {"boss", "inventory", "accounting", "facilities", "customer_service"}:
        raise ToolError("invalid: approved_by must be the name of the person approving, not an agent.")
    with closing(connect_rw()) as con:
        ensure_pending_table(con)
        con.execute("BEGIN IMMEDIATE")  # holds the write lock, so two approvals can't interleave
        try:
            txn = transaction_row(con, transaction_id)
            if txn is None:
                raise ToolError(f"not_found: No prepared transaction with id {transaction_id}.")
            if txn.status != "pending":
                raise ToolError(f"already_approved: Transaction {txn.id} was already approved by {txn.approved_by} on "
                                f"{txn.approved_at} as payment {txn.payment_id}. Nothing was charged again.")
            today = shop_date(con) or date.today().isoformat()
            if txn.kind == "invoice":
                bill = con.execute("SELECT amount, status FROM invoices WHERE id = ?", (txn.ref_id,)).fetchone()
                if bill is None or bill["status"] != "open":
                    raise ToolError(f"conflict: Invoice {txn.ref_id} is no longer open; it may have been paid already.")
                if round(bill["amount"], 2) != round(txn.amount, 2):
                    raise ToolError(f"conflict: Invoice {txn.ref_id} is now ${bill['amount']:,.2f}, not the ${txn.amount:,.2f} prepared.")
            elif txn.kind == "rent":
                lease = con.execute("SELECT next_due FROM leases WHERE id = ?", (txn.ref_id,)).fetchone()
                if lease is None or lease["next_due"] != txn.ref_due:
                    raise ToolError(f"conflict: Rent for lease {txn.ref_id} due {txn.ref_due} has already been paid.")
            balance = checking_balance(con)
            if balance < txn.amount:
                raise ToolError(f"insufficient_funds: Checking has ${balance:,.2f}, less than the ${txn.amount:,.2f} needed.")
            ref = txn.id if txn.kind == "purchase" else txn.ref_id
            cur = con.execute("INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
                              "VALUES (?, ?, ?, 'checking', ?, ?)", (txn.kind, ref, txn.amount, today, who))
            payment_id = cur.lastrowid
            con.execute("UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = 'checking'", (txn.amount, today))
            if txn.kind == "invoice":
                con.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (txn.ref_id,))
                effect = f"Invoice {txn.ref_id} marked paid."
            elif txn.kind == "rent":
                next_due = add_month(txn.ref_due)
                con.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, txn.ref_id))
                effect = f"Lease {txn.ref_id} next_due moved from {txn.ref_due} to {next_due}."
            else:
                effect = f"Vendor paid for {txn.qty} x {txn.sku} size {txn.size}. Stock arrives after the vendor's lead time; inventory is unchanged until then."
            con.execute("UPDATE pending_transactions SET status = 'approved', approved_by = ?, approved_at = ?, payment_id = ? "
                        "WHERE id = ? AND status = 'pending'", (who, today, payment_id, txn.id))
            if txn.ticket_id is not None:
                row = con.execute("SELECT notes FROM tickets WHERE id = ?", (txn.ticket_id,)).fetchone()
                if row is not None:
                    line = f"[{today} approved by {scrub(who)}] Payment {payment_id}: {txn.description}"
                    con.execute("UPDATE tickets SET notes = ? WHERE id = ?", (f"{row['notes']}\n{line}" if row["notes"] else line, txn.ticket_id))
            after = round(balance - txn.amount, 2)
            approved = transaction_row(con, txn.id)
            con.execute("COMMIT")
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
    warning = (f"Checking is down to ${after:,.2f}, under the $500 warning line." if after < 500 else None)
    return ApprovalReceipt(transaction=approved, payment_id=payment_id, amount=txn.amount, balance_before=balance,
                           balance_after=after, effect=effect, warning=warning)


if HUMAN_APPROVALS:  # only the FastAPI backend's own connection sets this; agents never see the tool
    mcp.tool(annotations=MONEY)(approve_transaction)


if __name__ == "__main__":
    mcp.run(show_banner=False)
