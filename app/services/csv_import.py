"""Import of Shopee order exports.

Shopee's CSV export columns vary by region/version, so instead of hardcoding
column names we let the user upload any CSV and manually map its columns to
the fields we need (sku, quantity, unit price, ...). The mapping step reuses
the same pricing.calculate_sale_item() used by manual sales, so imported
sales get the exact same kind of price/fee snapshot.
"""

import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import MarginProfile, Product, Sale, SaleItem, StockMovement
from app.services.pricing import calculate_sale_item, to_cents

REQUIRED_FIELDS = ("sku", "quantity", "unit_price")
OPTIONAL_FIELDS = ("order_number", "product_name", "sale_date")
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS


def _import_path(upload_folder: str, token: str) -> str:
    safe_token = secure_filename(token)
    return f"{upload_folder}/import_{safe_token}.csv"


def save_upload(upload_folder: str, file_storage) -> tuple[str, list[str], list[dict]]:
    """Persist the uploaded file and return (token, header, preview_rows)."""
    token = uuid.uuid4().hex
    path = _import_path(upload_folder, token)

    raw = file_storage.read()
    text = raw.decode("utf-8-sig", errors="replace")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    preview_rows = []
    for i, row in enumerate(reader):
        if i >= 5:
            break
        preview_rows.append(row)

    return token, header, preview_rows


def _read_rows(upload_folder: str, token: str):
    path = _import_path(upload_folder, token)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return list(csv.DictReader(io.StringIO(text)))


def read_preview(upload_folder: str, token: str, limit: int = 5) -> tuple[list[str], list[dict]]:
    """Re-read a previously saved upload's header + first `limit` rows.

    Raises FileNotFoundError if the token doesn't correspond to a saved file
    (e.g. the upload expired or was never created).
    """
    path = _import_path(upload_folder, token)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    preview_rows = []
    for i, row in enumerate(reader):
        if i >= limit:
            break
        preview_rows.append(row)
    return header, preview_rows


@dataclass
class ImportRowError:
    row_number: int
    reason: str


@dataclass
class ImportResult:
    sales_created: int = 0
    products_created: int = 0
    errors: list[ImportRowError] = field(default_factory=list)


def run_import(
    *,
    upload_folder: str,
    token: str,
    column_mapping: dict[str, str],
    margin_profile_id: int,
    create_missing_products: bool,
) -> ImportResult:
    rows = _read_rows(upload_folder, token)
    margin_profile = db.get_or_404(MarginProfile, margin_profile_id)
    result = ImportResult()

    for i, row in enumerate(rows, start=2):  # row 1 is the header
        try:
            sku = row.get(column_mapping.get("sku", ""), "").strip()
            qty_raw = row.get(column_mapping.get("quantity", ""), "").strip()
            price_raw = row.get(column_mapping.get("unit_price", ""), "").strip()

            if not sku or not qty_raw or not price_raw:
                result.errors.append(ImportRowError(i, "SKU, quantidade ou preço em branco."))
                continue

            quantity = int(float(qty_raw))
            unit_price_cents = to_cents(price_raw)

            order_number = None
            if column_mapping.get("order_number"):
                order_number = row.get(column_mapping["order_number"], "").strip() or None

            sale_date = datetime.now(timezone.utc)
            if column_mapping.get("sale_date"):
                raw_date = row.get(column_mapping["sale_date"], "").strip()
                sale_date = _parse_date(raw_date) or sale_date

            product = Product.query.filter_by(sku=sku).first()
            if product is None:
                if not create_missing_products:
                    result.errors.append(ImportRowError(i, f"SKU '{sku}' não encontrado."))
                    continue
                product_name = sku
                if column_mapping.get("product_name"):
                    product_name = row.get(column_mapping["product_name"], "").strip() or sku
                product = Product(
                    sku=sku,
                    name=product_name,
                    current_price_cents=unit_price_cents,
                    current_cost_cents=0,
                    stock_qty=0,
                )
                db.session.add(product)
                db.session.flush()
                result.products_created += 1

            calc = calculate_sale_item(
                quantity=quantity,
                unit_price_cents=unit_price_cents,
                unit_cost_cents=product.current_cost_cents,
                platform_fee_pct=margin_profile.platform_fee_pct,
                fixed_fee_cents=margin_profile.fixed_fee_cents,
                shipping_cost_cents=margin_profile.shipping_cost_cents,
                other_fee_pct=margin_profile.other_fee_pct,
            )

            sale = Sale(
                order_number=order_number,
                platform="Shopee",
                sale_date=sale_date,
                margin_profile_id=margin_profile.id,
                source="csv_import",
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
            db.session.add(
                StockMovement(product_id=product.id, delta_qty=-quantity, reason="venda_import")
            )

            result.sales_created += 1
        except (ValueError, KeyError) as exc:
            result.errors.append(ImportRowError(i, str(exc)))

    db.session.commit()
    return result


def _parse_date(raw: str):
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None
