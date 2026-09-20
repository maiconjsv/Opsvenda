import io
from pathlib import Path

from werkzeug.datastructures import FileStorage

from app.models import MarginProfile, Product
from app.services import csv_import

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


def test_run_import_matches_existing_product_and_creates_missing(db, tmp_path):
    existing = Product(sku="ABC123", name="Camiseta Azul", current_price_cents=2500, current_cost_cents=1000, stock_qty=100)
    profile = MarginProfile(name="Shopee Padrao", platform_fee_pct=0.10)
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


def test_run_import_skips_unknown_sku_when_not_creating(db, tmp_path):
    profile = MarginProfile(name="Shopee Padrao", platform_fee_pct=0.10)
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
    )

    assert result.sales_created == 0
    assert result.products_created == 0
    assert len(result.errors) == 3
