from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.blueprints.products import bp
from app.extensions import db
from app.models import Product, StockMovement
from app.services.pricing import to_cents


@bp.route("/")
@login_required
def index():
    query = request.args.get("q", "").strip()
    show_inactive = request.args.get("inactive") == "1"

    q = Product.query
    if not show_inactive:
        q = q.filter_by(active=True)
    if query:
        like = f"%{query}%"
        q = q.filter(db.or_(Product.name.ilike(like), Product.sku.ilike(like)))

    products = q.order_by(Product.name).all()
    return render_template(
        "products/index.html", products=products, query=query, show_inactive=show_inactive
    )


@bp.route("/novo", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        error = _validate_product_form(request.form)
        if error:
            flash(error, "danger")
            return render_template("products/form.html", product=None, form=request.form)

        product = Product(
            sku=request.form["sku"].strip() or None,
            name=request.form["name"].strip(),
            current_price_cents=to_cents(request.form["price"]),
            current_cost_cents=to_cents(request.form.get("cost") or 0),
            stock_qty=int(request.form.get("stock_qty") or 0),
        )
        db.session.add(product)
        db.session.flush()

        if product.stock_qty:
            db.session.add(
                StockMovement(
                    product_id=product.id,
                    delta_qty=product.stock_qty,
                    reason="estoque_inicial",
                )
            )
        db.session.commit()
        flash(f"Produto '{product.name}' criado.", "success")
        return redirect(url_for("products.index"))

    return render_template("products/form.html", product=None, form=None)


@bp.route("/<int:product_id>/editar", methods=["GET", "POST"])
@login_required
def edit(product_id):
    product = db.get_or_404(Product, product_id)

    if request.method == "POST":
        error = _validate_product_form(request.form, current_sku=product.sku)
        if error:
            flash(error, "danger")
            return render_template("products/form.html", product=product, form=request.form)

        product.sku = request.form["sku"].strip() or None
        product.name = request.form["name"].strip()
        product.current_price_cents = to_cents(request.form["price"])
        product.current_cost_cents = to_cents(request.form.get("cost") or 0)
        db.session.commit()
        flash(f"Produto '{product.name}' atualizado. Vendas anteriores não são afetadas.", "success")
        return redirect(url_for("products.index"))

    return render_template("products/form.html", product=product, form=None)


@bp.route("/<int:product_id>/estoque", methods=["POST"])
@login_required
def adjust_stock(product_id):
    product = db.get_or_404(Product, product_id)
    try:
        delta = int(request.form["delta_qty"])
    except (KeyError, ValueError):
        flash("Quantidade inválida.", "danger")
        return redirect(url_for("products.edit", product_id=product.id))

    if delta == 0:
        flash("Informe uma quantidade diferente de zero.", "warning")
        return redirect(url_for("products.edit", product_id=product.id))

    reason = request.form.get("reason", "ajuste")
    notes = request.form.get("notes", "").strip() or None

    product.stock_qty += delta
    db.session.add(StockMovement(product_id=product.id, delta_qty=delta, reason=reason, notes=notes))
    db.session.commit()
    flash("Estoque atualizado.", "success")
    return redirect(url_for("products.edit", product_id=product.id))


@bp.route("/<int:product_id>/desativar", methods=["POST"])
@login_required
def deactivate(product_id):
    product = db.get_or_404(Product, product_id)
    product.active = False
    db.session.commit()
    flash(f"Produto '{product.name}' desativado.", "info")
    return redirect(url_for("products.index"))


@bp.route("/<int:product_id>/ativar", methods=["POST"])
@login_required
def activate(product_id):
    product = db.get_or_404(Product, product_id)
    product.active = True
    db.session.commit()
    flash(f"Produto '{product.name}' reativado.", "info")
    return redirect(url_for("products.index"))


def _validate_product_form(form, current_sku=None):
    sku = form.get("sku", "").strip()
    name = form.get("name", "").strip()
    price = form.get("price", "").strip()

    if not name or not price:
        return "Nome e preço são obrigatórios."

    try:
        to_cents(price)
    except ValueError:
        return "Preço inválido."

    cost = form.get("cost", "").strip()
    if cost:
        try:
            to_cents(cost)
        except ValueError:
            return "Custo inválido."

    if sku and sku != current_sku:
        existing = Product.query.filter_by(sku=sku).first()
        if existing:
            return f"Já existe um produto com o SKU '{sku}'."

    return None
