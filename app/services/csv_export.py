import csv
import io

from app.services.pricing import from_cents


def sales_to_csv(sale_items) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "data_venda",
            "pedido",
            "sku",
            "produto",
            "quantidade",
            "preco_unitario",
            "custo_unitario",
            "receita_bruta",
            "taxas_totais",
            "custo_total",
            "lucro_liquido",
            "margem_pct",
            "status",
            "origem",
        ]
    )
    for item in sale_items:
        writer.writerow(
            [
                item.sale.sale_date.strftime("%Y-%m-%d %H:%M"),
                item.sale.order_number or "",
                item.product_sku_snapshot,
                item.product_name_snapshot,
                item.quantity,
                f"{from_cents(item.unit_price_snapshot_cents):.2f}",
                f"{from_cents(item.unit_cost_snapshot_cents):.2f}",
                f"{from_cents(item.gross_total_cents):.2f}",
                f"{from_cents(item.total_fees_cents):.2f}",
                f"{from_cents(item.total_cost_cents):.2f}",
                f"{from_cents(item.net_profit_cents):.2f}",
                f"{item.margin_pct * 100:.2f}",
                item.sale.status,
                item.sale.source,
            ]
        )
    return buffer.getvalue()
