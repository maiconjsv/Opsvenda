from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.blueprints.sales import bp
from app.extensions import db
from app.models import MarginProfile, Product, Sale, SaleItem, StockMovement
from app.models.sale import STATUS_CANCELLED
from app.services import csv_import
from app.services.pricing import calculate_sale_item, to_cents


@bp.route("/")
@login_required
def index():
    sales = Sale.query.order_by(Sale.sale_date.desc()).limit(200).all()
    return render_template("sales/index.html", sales=sales)


@bp.route("/nova", methods=["GET", "POST"])
@login_required
def create():
    products = Product.query.filter_by(active=True).order_by(Product.name).all()
    profiles = MarginProfile.query.filter_by(active=True).order_by(MarginProfile.name).all()

    if request.method == "POST":
        error, sale = _create_manual_sale(request.form)
        if error:
            flash(error, "danger")
            return render_template(
                "sales/form.html", products=products, profiles=profiles, form=request.form
            )
        flash(f"Venda #{sale.id} registrada.", "success")
        return redirect(url_for("sales.detail", sale_id=sale.id))

    return render_template("sales/form.html", products=products, profiles=profiles, form=None)


def _create_manual_sale(form):
    try:
        product_id = int(form["product_id"])
        quantity = int(form["quantity"])
        margin_profile_id = int(form["margin_profile_id"])
    except (KeyError, ValueError):
        return "Preencha produto, quantidade e perfil de margem corretamente.", None

    if quantity <= 0:
        return "A quantidade deve ser maior que zero.", None

    product = db.session.get(Product, product_id)
    if product is None:
        return "Produto não encontrado.", None

    margin_profile = db.session.get(MarginProfile, margin_profile_id)
    if margin_profile is None:
        return "Perfil de margem não encontrado.", None

    unit_price_raw = form.get("unit_price", "").strip()
    unit_cost_raw = form.get("unit_cost", "").strip()
    try:
        unit_price_cents = to_cents(unit_price_raw) if unit_price_raw else product.current_price_cents
        unit_cost_cents = to_cents(unit_cost_raw) if unit_cost_raw else product.current_cost_cents
    except ValueError:
        return "Preço ou custo inválido.", None

    calc = calculate_sale_item(
        quantity=quantity,
        unit_price_cents=unit_price_cents,
        unit_cost_cents=unit_cost_cents,
        platform_fee_pct=margin_profile.platform_fee_pct,
        fixed_fee_cents=margin_profile.fixed_fee_cents,
        shipping_cost_cents=margin_profile.shipping_cost_cents,
        other_fee_pct=margin_profile.other_fee_pct,
    )

    sale = Sale(
        order_number=form.get("order_number", "").strip() or None,
        margin_profile_id=margin_profile.id,
        notes=form.get("notes", "").strip() or None,
        source="manual",
    )
    sale.items.append(
        SaleItem(
            product_id=product.id,
            product_name_snapshot=product.name,
            product_sku_snapshot=product.sku,
            quantity=calc.quantity,
            unit_price_snapshot_cents=calc.unit_price_cents,
            unit_cost_snapshot_cents=calc.unit_cost_cents,
            platform_fee_pct_snapshot=calc.platform_fee_pct,
            fixed_fee_snapshot_cents=calc.fixed_fee_cents,
            shipping_cost_snapshot_cents=calc.shipping_cost_cents,
            other_fee_pct_snapshot=calc.other_fee_pct,
            gross_total_cents=calc.gross_total_cents,
            total_fees_cents=calc.total_fees_cents,
            total_cost_cents=calc.total_cost_cents,
            net_profit_cents=calc.net_profit_cents,
        )
    )
    db.session.add(sale)

    product.stock_qty -= quantity
    db.session.add(StockMovement(product_id=product.id, delta_qty=-quantity, reason="venda"))

    db.session.commit()
    return None, sale


@bp.route("/<int:sale_id>")
@login_required
def detail(sale_id):
    sale = db.get_or_404(Sale, sale_id)
    return render_template("sales/detail.html", sale=sale)


@bp.route("/<int:sale_id>/cancelar", methods=["POST"])
@login_required
def cancel(sale_id):
    sale = db.get_or_404(Sale, sale_id)
    if sale.status == STATUS_CANCELLED:
        flash("Essa venda já está cancelada.", "warning")
        return redirect(url_for("sales.detail", sale_id=sale.id))

    for item in sale.items:
        if item.product:
            item.product.stock_qty += item.quantity
            db.session.add(
                StockMovement(
                    product_id=item.product_id, delta_qty=item.quantity, reason="estorno"
                )
            )
    sale.status = STATUS_CANCELLED
    db.session.commit()
    flash(f"Venda #{sale.id} cancelada e estoque estornado.", "info")
    return redirect(url_for("sales.detail", sale_id=sale.id))


# ---- Import CSV wizard ----


@bp.route("/importar", methods=["GET", "POST"])
@login_required
def import_start():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("Selecione um arquivo CSV.", "danger")
            return redirect(url_for("sales.import_start"))

        token, _header, _preview_rows = csv_import.save_upload(
            current_app.config["UPLOAD_FOLDER"], file
        )
        return redirect(url_for("sales.import_map", token=token))

    return render_template("sales/import_start.html")


@bp.route("/importar/<token>/mapear", methods=["GET", "POST"])
@login_required
def import_map(token):
    try:
        header, preview_rows = csv_import.read_preview(current_app.config["UPLOAD_FOLDER"], token)
    except FileNotFoundError:
        flash("Upload expirado ou inválido, envie o arquivo novamente.", "danger")
        return redirect(url_for("sales.import_start"))

    profiles = MarginProfile.query.filter_by(active=True).order_by(MarginProfile.name).all()

    if request.method == "POST":
        mapping = {
            "sku": request.form.get("map_sku", ""),
            "quantity": request.form.get("map_quantity", ""),
            "unit_price": request.form.get("map_unit_price", ""),
            "order_number": request.form.get("map_order_number", ""),
            "product_name": request.form.get("map_product_name", ""),
            "sale_date": request.form.get("map_sale_date", ""),
        }
        if not mapping["sku"] or not mapping["quantity"] or not mapping["unit_price"]:
            flash("Mapeie ao menos SKU, quantidade e preço unitário.", "danger")
            return render_template(
                "sales/import_map.html", token=token, header=header, preview_rows=preview_rows,
                profiles=profiles,
            )

        try:
            margin_profile_id = int(request.form["margin_profile_id"])
        except (KeyError, ValueError):
            flash("Selecione um perfil de margem válido.", "danger")
            return render_template(
                "sales/import_map.html", token=token, header=header, preview_rows=preview_rows,
                profiles=profiles,
            )
        create_missing = request.form.get("create_missing_products") == "on"

        result = csv_import.run_import(
            upload_folder=current_app.config["UPLOAD_FOLDER"],
            token=token,
            column_mapping=mapping,
            margin_profile_id=margin_profile_id,
            create_missing_products=create_missing,
        )
        return render_template("sales/import_result.html", result=result)

    return render_template(
        "sales/import_map.html", token=token, header=header, preview_rows=preview_rows,
        profiles=profiles,
    )
