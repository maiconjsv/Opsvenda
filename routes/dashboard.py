from datetime import datetime, timedelta

from flask import Blueprint, Response, current_app, render_template, request, send_file
from flask_login import current_user, login_required

from models import Product, Sale, SaleItem
from models.sale import STATUS_CANCELLED
from scoping import scoped_query
from services.backup import create_backup
from services.csv_export import sales_to_csv
from services.pricing import from_cents

bp = Blueprint("dashboard", __name__, url_prefix="/")


def _items_query(date_from, date_to, product_id):
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

    return query.order_by(Sale.sale_date.desc())


def _filtered_items(args):
    return _items_query(
        args.get("date_from", "").strip(),
        args.get("date_to", "").strip(),
        args.get("product_id", "").strip(),
    )


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

    prev_items = _items_query(
        prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d"), product_id
    ).all()
    return sum(i.net_profit_cents for i in prev_items)


def _build_insights(items, profit_total_cents, date_from, date_to, product_id):
    loss_items = [i for i in items if i.net_profit_cents < 0]
    loss_total_cents = -sum(i.net_profit_cents for i in loss_items)

    profit_by_product = {}
    for i in items:
        profit_by_product[i.product_name_snapshot] = (
            profit_by_product.get(i.product_name_snapshot, 0) + i.net_profit_cents
        )

    top_product = None
    bottom_product = None
    if profit_by_product:
        top_name, top_cents = max(profit_by_product.items(), key=lambda kv: kv[1])
        top_product = {"name": top_name, "profit": from_cents(top_cents)}
        bottom_name, bottom_cents = min(profit_by_product.items(), key=lambda kv: kv[1])
        if bottom_cents < 0:
            bottom_product = {"name": bottom_name, "loss": from_cents(-bottom_cents)}

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
        "loss_count": len(loss_items),
        "loss_total": from_cents(loss_total_cents),
        "top_product": top_product,
        "bottom_product": bottom_product,
        "previous_profit": from_cents(previous_profit_cents) if previous_profit_cents is not None else None,
        "profit_change_pct": profit_change_pct,
    }


@bp.route("/")
@login_required
def index():
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    product_id = request.args.get("product_id", "").strip()

    items = _items_query(date_from, date_to, product_id).all()

    gross_total_cents = sum(i.gross_total_cents for i in items)
    fees_total_cents = sum(i.total_fees_cents for i in items)
    cost_total_cents = sum(i.total_cost_cents for i in items)
    profit_total_cents = sum(i.net_profit_cents for i in items)
    units_sold = sum(i.quantity for i in items)
    avg_margin_pct = (profit_total_cents / gross_total_cents * 100) if gross_total_cents else 0.0

    kpis = {
        "gross_total": from_cents(gross_total_cents),
        "fees_total": from_cents(fees_total_cents),
        "cost_total": from_cents(cost_total_cents),
        "profit_total": from_cents(profit_total_cents),
        "units_sold": units_sold,
        "avg_margin_pct": avg_margin_pct,
    }

    insights = _build_insights(items, profit_total_cents, date_from, date_to, product_id)

    products = scoped_query(Product).order_by(Product.name).all()

    return render_template(
        "dashboard/index.html",
        items=items[:100],
        kpis=kpis,
        insights=insights,
        products=products,
        filters=request.args,
        total_rows=len(items),
    )


@bp.route("/exportar.csv")
@login_required
def export_csv():
    items = _filtered_items(request.args).all()
    csv_content = sales_to_csv(items)
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=vendas.csv"},
    )


@bp.route("/backup")
@login_required
def backup():
    backup_path = create_backup(current_app.config["INSTANCE_DIR"])
    if backup_path is None:
        return Response("Nenhum banco de dados encontrado ainda.", status=404)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    return send_file(
        backup_path,
        as_attachment=True,
        download_name=f"opsvenda_backup_{timestamp}.db",
    )
