"""Excel de la tienda (openpyxl)."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


def libro(hojas):
    """hojas: [(nombre, encabezados, filas)] -> bytes .xlsx"""
    wb = Workbook()
    wb.remove(wb.active)
    for nombre, encabezados, filas in hojas:
        ws = wb.create_sheet(nombre[:31])
        ws.append(encabezados)
        for f in filas:
            ws.append(list(f))
        for fila in ws.iter_rows():
            for c in fila:
                if isinstance(c.value, str):
                    c.data_type = "s"
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="253449")
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max(len(str(c.value or "")) for c in col) + 2, 42)
        ws.freeze_panes = "A2"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()