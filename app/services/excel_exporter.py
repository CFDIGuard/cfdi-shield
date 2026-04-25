from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


HEADER_FILL = PatternFill(fill_type="solid", fgColor="DCEBFF")
HEADER_FONT = Font(bold=True)
THIN_BORDER = Border(
    left=Side(style="thin", color="D0D7E2"),
    right=Side(style="thin", color="D0D7E2"),
    top=Side(style="thin", color="D0D7E2"),
    bottom=Side(style="thin", color="D0D7E2"),
)
MXN_FORMAT = '$#,##0.00'
PERCENT_FORMAT = '0.00%'


def _apply_header_style(row) -> None:
    for cell in row:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = THIN_BORDER


def _apply_borders(ws) -> None:
    for row in ws.iter_rows():
        for cell in row:
            if cell.value not in (None, ""):
                cell.border = THIN_BORDER


def _auto_width(ws) -> None:
    for column_cells in ws.columns:
        max_length = 0
        column_index = column_cells[0].column
        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            max_length = max(max_length, len(value))
        ws.column_dimensions[get_column_letter(column_index)].width = min(max(max_length + 2, 12), 42)


def _write_rows(ws, headers: list[str], rows: list[list[object]]) -> None:
    ws.append(headers)
    _apply_header_style(ws[1])
    for row in rows:
        ws.append(row)
    _apply_borders(ws)
    _auto_width(ws)


def generate_excel_report(reports_bundle: dict[str, object]) -> bytes:
    summary = reports_bundle["summary"]
    reports = reports_bundle["reports"]

    wb = Workbook()
    ws_resumen = wb.active
    ws_resumen.title = "RESUMEN"
    resumen_headers = ["Indicador", "Valor"]
    resumen_rows = [
        ["Total facturado", summary["total_facturado"]],
        ["Facturas", summary["facturas"]],
        ["Vigentes", summary["vigentes"]],
        ["Canceladas", summary["canceladas"]],
        ["Proveedores unicos", summary["proveedores_unicos"]],
    ]
    _write_rows(ws_resumen, resumen_headers, resumen_rows)
    for cell in ws_resumen["B"][1:]:
        if isinstance(cell.value, (int, float)) and ws_resumen[f"A{cell.row}"].value == "Total facturado":
            cell.number_format = MXN_FORMAT

    ws_control = wb.create_sheet("CONTROL")
    control_headers = ["UUID", "RFC emisor", "Nombre", "Monto", "IVA", "Estatus SAT", "Riesgo"]
    control_rows = [
        [
            row.get("uuid"),
            row.get("rfc_emisor"),
            row.get("razon_social"),
            row.get("total"),
            row.get("iva"),
            row.get("estatus_sat"),
            row.get("riesgo"),
        ]
        for row in reports["control"]
    ]
    _write_rows(ws_control, control_headers, control_rows)
    for cell in ws_control["D"][1:] + ws_control["E"][1:]:
        cell.number_format = MXN_FORMAT

    ws_proveedores = wb.create_sheet("PROVEEDORES")
    proveedores_headers = [
        "RFC",
        "Nombre",
        "Total facturado",
        "Facturas",
        "Canceladas",
        "% canceladas",
        "IVA total",
        "Score",
        "Nivel",
    ]
    proveedores_rows = [
        [
            row.get("rfc_emisor"),
            row.get("razon_social"),
            row.get("total_facturado"),
            row.get("facturas"),
            row.get("canceladas"),
            (row.get("porcentaje_canceladas", 0) or 0) / 100,
            row.get("iva_total"),
            row.get("score_riesgo"),
            row.get("nivel_riesgo"),
        ]
        for row in reports["proveedores"]
    ]
    _write_rows(ws_proveedores, proveedores_headers, proveedores_rows)
    for cell in ws_proveedores["C"][1:] + ws_proveedores["G"][1:]:
        cell.number_format = MXN_FORMAT
    for cell in ws_proveedores["F"][1:]:
        cell.number_format = PERCENT_FORMAT

    ws_riesgos = wb.create_sheet("RIESGOS")
    riesgos_headers = ["UUID", "Tipo riesgo", "Nivel", "Detalle"]
    riesgos_rows = [
        [
            row.get("uuid"),
            row.get("detalle_riesgo") or row.get("riesgo") or "-",
            row.get("riesgo"),
            row.get("detalle_riesgo") or "-",
        ]
        for row in reports["riesgos"]
    ]
    _write_rows(ws_riesgos, riesgos_headers, riesgos_rows)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
