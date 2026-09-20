from datetime import datetime, timedelta

from flask import Response, render_template, request
from flask_login import login_required

from app.blueprints.dashboard import bp
from app.models import Product, Sale, SaleItem
from app.models.sale import STATUS_CANCELLED
from app.services.csv_export import sales_to_csv
from app.services.pricing import from_cents


def _filtered_items(args):
    query = SaleItem.query.join(Sale).filter(Sale.status != STATUS_CANCELLED)

    date_from = args.get("date_from", "").strip()
    date_to = args.get("date_to", "").strip()
    product_id = args.get("product_id", "").strip()

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


@bp.route("/")
@login_required
def index():
    items = _filtered_items(request.args).all()

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

    products = Product.query.order_by(Product.name).all()

    return render_template(
        "dashboard/index.html",
        items=items[:100],
        kpis=kpis,
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
