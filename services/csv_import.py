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

from flask import abort
from werkzeug.utils import secure_filename

from extensions import db
from models import MarginProfile, Product, Sale, SaleItem
from services.pricing import calculate_sale_item, to_cents
from services.stock import adjust_stock

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
    duplicates_skipped: int = 0
    # False when no order-number column was mapped: without it duplicates
    # can't be detected, and the result page warns about re-importing.
    dedup_enabled: bool = True
    # Names of products created with an unknown cost (cost_pending).
    pending_cost_products: list[str] = field(default_factory=list)
    errors: list[ImportRowError] = field(default_factory=list)


def _existing_order_keys(company_id: int, order_numbers: set[str]) -> set[tuple[str, str]]:
    """(order_number, sku) pairs already imported/registered for the company."""
    if not order_numbers:
        return set()
    rows = (
        db.session.query(Sale.order_number, SaleItem.product_sku_snapshot)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .filter(Sale.company_id == company_id, Sale.order_number.in_(order_numbers))
        .all()
    )
    return {(order_number, sku) for order_number, sku in rows}


def run_import(
    *,
    upload_folder: str,
    token: str,
    column_mapping: dict[str, str],
    margin_profile_id: int,
    create_missing_products: bool,
    company_id: int,
) -> ImportResult:
    rows = _read_rows(upload_folder, token)
    margin_profile = MarginProfile.query.filter_by(id=margin_profile_id, company_id=company_id).first()
    if margin_profile is None:
        abort(404)

    def cell(row, field_name):
        column = column_mapping.get(field_name)
        return (row.get(column) or "").strip() if column else ""

    result = ImportResult(dedup_enabled=bool(column_mapping.get("order_number")))

    # One query each for products and already-imported orders, instead of one per row.
    skus = {cell(row, "sku") for row in rows} - {""}
    products_by_sku = {
        p.sku: p
        for p in Product.query.filter(Product.company_id == company_id, Product.sku.in_(skus))
    } if skus else {}
    seen_keys = _existing_order_keys(company_id, {cell(row, "order_number") for row in rows} - {""})

    for i, row in enumerate(rows, start=2):  # row 1 is the header
        try:
            sku = cell(row, "sku")
            qty_raw = cell(row, "quantity")
            price_raw = cell(row, "unit_price")

            if not sku or not qty_raw or not price_raw:
                result.errors.append(ImportRowError(i, "SKU, quantidade ou preço em branco."))
                continue

            quantity = int(float(qty_raw))
            unit_price_cents = to_cents(price_raw)

            # Same order + same SKU already registered (earlier import, or
            # earlier in this same file): re-importing must not duplicate it.
            order_number = cell(row, "order_number") or None
            if order_number and (order_number, sku) in seen_keys:
                result.duplicates_skipped += 1
                continue

            sale_date = _parse_date(cell(row, "sale_date")) or datetime.now(timezone.utc)

            product = products_by_sku.get(sku)
            if product is None:
                if not create_missing_products:
                    result.errors.append(ImportRowError(i, f"SKU '{sku}' não encontrado."))
                    continue
                product = Product(
                    company_id=company_id,
                    sku=sku,
                    name=cell(row, "product_name") or sku,
                    current_price_cents=unit_price_cents,
                    current_cost_cents=0,
                    cost_pending=True,
                    stock_qty=0,
                )
                db.session.add(product)
                db.session.flush()
                products_by_sku[sku] = product
                result.products_created += 1
                result.pending_cost_products.append(product.name)

            calc = calculate_sale_item(
                quantity=quantity,
                unit_price_cents=unit_price_cents,
                unit_cost_cents=product.current_cost_cents,
                platform_fee_pct=margin_profile.platform_fee_pct,
                fixed_fee_cents=margin_profile.fixed_fee_cents,
                other_fee_pct=margin_profile.other_fee_pct,
            )

            sale = Sale(
                company_id=company_id,
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
                    other_fee_pct_snapshot=calc.other_fee_pct,
                    gross_total_cents=calc.gross_total_cents,
                    total_fees_cents=calc.total_fees_cents,
                    total_cost_cents=calc.total_cost_cents,
                    net_profit_cents=calc.net_profit_cents,
                    cost_pending=product.cost_pending,
                )
            )
            db.session.add(sale)

            adjust_stock(product.id, -quantity, "venda_import")

            if order_number:
                seen_keys.add((order_number, sku))
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
