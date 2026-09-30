from datetime import datetime, timedelta

from flask import Blueprint, Response, render_template, request, stream_with_context
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import contains_eager

from models import Product, Sale, SaleItem
from models.sale import STATUS_CANCELLED
from scoping import scoped_query
from services.csv_export import iter_sales_csv
from services.pricing import from_cents

bp = Blueprint("dashboard", __name__, url_prefix="/")

TABLE_ROWS = 100


def _items_query(date_from, date_to, product_id):
    """Non-cancelled sale items of the current company matching the filters.
    Callers aggregate it in SQL (with_entities) or page it - never .all() on
    the unbounded query.
    """
    query = SaleItem.query.join(Sale).filter(
        Sale.status != STATUS_CANCELLED, Sale.company_id == current_user.company_id
    )

    if date_from:
        try:
            query = query.filter(Sale.sale_date >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Sale.sale_date < end)
        except ValueError:
            pass
    if product_id:
        try:
            query = query.filter(SaleItem.product_id == int(product_id))
        except ValueError:
            pass

    return query


def _sum(column):
    return func.coalesce(func.sum(column), 0)


def _previous_period_profit_cents(date_from, date_to, product_id):
    """Sum of net profit for the period of equal length immediately before
    [date_from, date_to], e.g. 8-14 Jan -> previous period is 1-7 Jan. Returns
    None if the dates can't be parsed (nothing to compare against).
    """
    try:
        start = datetime.strptime(date_from, "%Y-%m-%d")
        end = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        return None

    period_length = (end - start) + timedelta(days=1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - period_length + timedelta(days=1)

    return _items_query(
        prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d"), product_id
    ).with_entities(_sum(SaleItem.net_profit_cents)).scalar()


def _build_insights(query, profit_total_cents, date_from, date_to, product_id):
    loss_count, loss_sum_cents = (
        query.filter(SaleItem.net_profit_cents < 0)
        .with_entities(func.count(SaleItem.id), _sum(SaleItem.net_profit_cents))
        .one()
    )

    profit_by_product = query.with_entities(
        SaleItem.product_name_snapshot, func.sum(SaleItem.net_profit_cents).label("profit")
    ).group_by(SaleItem.product_name_snapshot)
    top = profit_by_product.order_by(func.sum(SaleItem.net_profit_cents).desc()).first()
    bottom = profit_by_product.order_by(func.sum(SaleItem.net_profit_cents).asc()).first()

    top_product = {"name": top[0], "profit": from_cents(top[1])} if top else None
    bottom_product = None
    if bottom and bottom[1] < 0:
        bottom_product = {"name": bottom[0], "loss": from_cents(-bottom[1])}

    pending_cost_count = (
        query.filter(SaleItem.cost_pending.is_(True)).with_entities(func.count(SaleItem.id)).scalar()
    )

    previous_profit_cents = None
    profit_change_pct = None
    if date_from and date_to:
        previous_profit_cents = _previous_period_profit_cents(date_from, date_to, product_id)
        if previous_profit_cents:
            profit_change_pct = (
                (profit_total_cents - previous_profit_cents) / abs(previous_profit_cents) * 100
            )

    return {
        "has_period_filter": bool(date_from and date_to),
        "loss_count": loss_count,
        "loss_total": from_cents(-loss_sum_cents),
        "top_product": top_product,
        "bottom_product": bottom_product,
        "previous_profit": from_cents(previous_profit_cents) if previous_profit_cents is not None else None,
        "profit_change_pct": profit_change_pct,
        "pending_cost_count": pending_cost_count,
    }


@bp.route("/")
@login_required
def index():
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    product_id = request.args.get("product_id", "").strip()

    query = _items_query(date_from, date_to, product_id)

    (
        gross_total_cents,
        fees_total_cents,
        cost_total_cents,
        profit_total_cents,
        units_sold,
        total_rows,
    ) = query.with_entities(
        _sum(SaleItem.gross_total_cents),
        _sum(SaleItem.total_fees_cents),
        _sum(SaleItem.total_cost_cents),
        _sum(SaleItem.net_profit_cents),
        _sum(SaleItem.quantity),
        func.count(SaleItem.id),
    ).one()
    avg_margin_pct = (profit_total_cents / gross_total_cents * 100) if gross_total_cents else 0.0

    kpis = {
        "gross_total": from_cents(gross_total_cents),
        "fees_total": from_cents(fees_total_cents),
        "cost_total": from_cents(cost_total_cents),
        "profit_total": from_cents(profit_total_cents),
        "units_sold": units_sold,
        "avg_margin_pct": avg_margin_pct,
    }

    insights = _build_insights(query, profit_total_cents, date_from, date_to, product_id)

    items = (
        query.options(contains_eager(SaleItem.sale))
        .order_by(Sale.sale_date.desc(), SaleItem.id.desc())
        .limit(TABLE_ROWS)
        .all()
    )

    products = scoped_query(Product).order_by(Product.name).all()

    return render_template(
        "dashboard/index.html",
        items=items,
        kpis=kpis,
        insights=insights,
        products=products,
        filters=request.args,
        total_rows=total_rows,
    )


@bp.route("/exportar.csv")
@login_required
def export_csv():
    items = (
        _items_query(
            request.args.get("date_from", "").strip(),
            request.args.get("date_to", "").strip(),
            request.args.get("product_id", "").strip(),
        )
        .options(contains_eager(SaleItem.sale))
        .order_by(Sale.sale_date.desc(), SaleItem.id.desc())
        .yield_per(1000)
    )
    # Streamed in batches of 1000 rows, so a large export never sits whole in memory.
    return Response(
        stream_with_context(iter_sales_csv(items)),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=vendas.csv"},
    )
