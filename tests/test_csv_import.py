import io
from pathlib import Path

from werkzeug.datastructures import FileStorage

from models import MarginProfile, Product, Sale, SaleItem
from services import csv_import

FIXTURE = Path(__file__).parent / "fixtures" / "shopee_orders_sample.csv"


def _upload_fixture(upload_folder):
    with open(FIXTURE, "rb") as f:
        storage = FileStorage(stream=io.BytesIO(f.read()), filename="shopee_orders_sample.csv")
    return csv_import.save_upload(upload_folder, storage)


def test_save_upload_returns_header_and_preview(tmp_path):
    token, header, preview_rows = _upload_fixture(str(tmp_path))

    assert "SKU" in header
    assert len(preview_rows) == 3
    assert preview_rows[0]["SKU"] == "ABC123"


def test_run_import_matches_existing_product_and_creates_missing(db, tmp_path, company):
    existing = Product(
        company_id=company.id, sku="ABC123", name="Camiseta Azul",
        current_price_cents=2500, current_cost_cents=1000, stock_qty=100,
    )
    profile = MarginProfile(company_id=company.id, name="Shopee Padrao", platform_fee_pct=0.10)
    db.session.add_all([existing, profile])
    db.session.commit()

    token, _header, _preview = _upload_fixture(str(tmp_path))

    mapping = {
        "sku": "SKU",
        "quantity": "Quantidade",
        "unit_price": "Preco Unitario",
        "order_number": "Numero do Pedido",
        "product_name": "Nome do Produto",
        "sale_date": "Data",
    }

    result = csv_import.run_import(
        upload_folder=str(tmp_path),
        token=token,
        column_mapping=mapping,
        margin_profile_id=profile.id,
        create_missing_products=True,
        company_id=company.id,
    )

    # Row 1 (ABC123) matches existing product -> sale created.
    # Row 2 (NEW-999) has no matching product -> created because create_missing_products=True.
    # Row 3 has a blank quantity -> recorded as an error, not imported.
    assert result.sales_created == 2
    assert result.products_created == 1
    assert len(result.errors) == 1
    assert result.errors[0].row_number == 4  # header is line 1, third data row is line 4

    db.session.refresh(existing)
    assert existing.stock_qty == 98  # 100 - 2 units sold in row 1


def test_run_import_skips_unknown_sku_when_not_creating(db, tmp_path, company):
    profile = MarginProfile(company_id=company.id, name="Shopee Padrao", platform_fee_pct=0.10)
    db.session.add(profile)
    db.session.commit()

    token, _header, _preview = _upload_fixture(str(tmp_path))

    mapping = {
        "sku": "SKU",
        "quantity": "Quantidade",
        "unit_price": "Preco Unitario",
    }

    result = csv_import.run_import(
        upload_folder=str(tmp_path),
        token=token,
        column_mapping=mapping,
        margin_profile_id=profile.id,
        create_missing_products=False,
        company_id=company.id,
    )

    assert result.sales_created == 0
    assert result.products_created == 0
    assert len(result.errors) == 3


FULL_MAPPING = {
    "sku": "SKU",
    "quantity": "Quantidade",
    "unit_price": "Preco Unitario",
    "order_number": "Numero do Pedido",
    "product_name": "Nome do Produto",
    "sale_date": "Data",
}


def _upload_text(upload_folder, text):
    storage = FileStorage(stream=io.BytesIO(text.encode("utf-8")), filename="pedidos.csv")
    token, _header, _preview = csv_import.save_upload(upload_folder, storage)
    return token


def _import(tmp_path, token, profile, company, mapping=FULL_MAPPING, create_missing=True):
    return csv_import.run_import(
        upload_folder=str(tmp_path),
        token=token,
        column_mapping=mapping,
        margin_profile_id=profile.id,
        create_missing_products=create_missing,
        company_id=company.id,
    )


def _existing_product_and_profile(db, company):
    existing = Product(
        company_id=company.id, sku="ABC123", name="Camiseta Azul",
        current_price_cents=2500, current_cost_cents=1000, stock_qty=100,
    )
    profile = MarginProfile(company_id=company.id, name="Shopee Padrao", platform_fee_pct=0.10)
    db.session.add_all([existing, profile])
    db.session.commit()
    return existing, profile


def test_reimporting_the_same_file_skips_already_imported_orders(db, tmp_path, company):
    existing, profile = _existing_product_and_profile(db, company)

    first = _import(tmp_path, _upload_fixture(str(tmp_path))[0], profile, company)
    second = _import(tmp_path, _upload_fixture(str(tmp_path))[0], profile, company)

    assert first.sales_created == 2
    assert second.sales_created == 0
    assert second.duplicates_skipped == 2
    assert second.products_created == 0
    assert Sale.query.count() == 2
    db.session.refresh(existing)
    assert existing.stock_qty == 98  # stock decremented only once


def test_duplicate_rows_inside_one_file_are_imported_once(db, tmp_path, company):
    existing, profile = _existing_product_and_profile(db, company)
    token = _upload_text(str(tmp_path), (
        "Numero do Pedido,SKU,Nome do Produto,Quantidade,Preco Unitario,Data\n"
        "PED-9,ABC123,Camiseta Azul,1,29.90,2026-01-10\n"
        "PED-9,ABC123,Camiseta Azul,1,29.90,2026-01-10\n"
    ))

    result = _import(tmp_path, token, profile, company)

    assert result.sales_created == 1
    assert result.duplicates_skipped == 1


def test_without_order_number_mapping_dedup_is_disabled(db, tmp_path, company):
    _existing, profile = _existing_product_and_profile(db, company)
    mapping = {"sku": "SKU", "quantity": "Quantidade", "unit_price": "Preco Unitario"}

    result = _import(tmp_path, _upload_fixture(str(tmp_path))[0], profile, company, mapping=mapping)

    assert result.dedup_enabled is False


def test_products_created_by_import_have_pending_cost(db, tmp_path, company):
    _existing, profile = _existing_product_and_profile(db, company)

    result = _import(tmp_path, _upload_fixture(str(tmp_path))[0], profile, company)

    created = Product.query.filter_by(sku="NEW-999").one()
    assert created.cost_pending is True
    assert result.pending_cost_products == ["Produto Novo"]
    items = {i.product_sku_snapshot: i for i in SaleItem.query.all()}
    assert items["NEW-999"].cost_pending is True
    assert items["ABC123"].cost_pending is False  # existing product, known cost
