import os
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn
from pptx import Presentation
from pptx.util import Inches as PptxInches, Pt as PptxPt
from pptx.dml.color import RGBColor as PptxRGBColor
from pptx.enum.text import PP_ALIGN

class OfficeTools:
    @staticmethod
    def create_excel(project_path: str, filename: str, sheets_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates a professionally formatted Excel spreadsheet (.xlsx).
        sheets_data is a list of dicts:
        [
            {
                "sheet_name": "Resumen Financiero",
                "headers": ["Concepto", "Q1", "Q2", "Q3", "Total"],
                "rows": [
                    ["Ingresos", 12000, 15000, 18000, "=SUM(B2:D2)"],
                    ["Gastos", 8000, 9500, 11000, "=SUM(B3:D3)"]
                ],
                "create_chart": True/False,
                "chart_title": "Comparativa"
            }
        ]
        """
        if not filename.endswith(".xlsx"):
            filename += ".xlsx"
        full_path = os.path.join(project_path, filename)
        
        wb = openpyxl.Workbook()
        # Remove default sheet
        wb.remove(wb.active)
        
        # Color palette: Elegant Deep Navy & Cool Slate
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        alt_row_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        regular_font = Font(name="Segoe UI", size=10)
        bold_font = Font(name="Segoe UI", size=10, bold=True)
        thin_border = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )
        
        for s_idx, s_info in enumerate(sheets_data):
            name = s_info.get("sheet_name", f"Hoja{s_idx + 1}")[:31]
            ws = wb.create_sheet(title=name)
            ws.views.sheetView[0].showGridLines = True
            
            headers = s_info.get("headers", [])
            rows = s_info.get("rows", [])
            
            # Write Headers
            for col_idx, header in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col_idx, value=str(header))
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = thin_border
            ws.row_dimensions[1].height = 28
            
            # Write Data Rows
            for r_idx, row in enumerate(rows, start=2):
                ws.row_dimensions[r_idx].height = 22
                for c_idx, val in enumerate(row, start=1):
                    cell = ws.cell(row=r_idx, column=c_idx, value=val)
                    cell.font = regular_font
                    cell.border = thin_border
                    
                    # Zebra striping
                    if r_idx % 2 == 1:
                        cell.fill = alt_row_fill
                        
                    # Alignment and formatting
                    if isinstance(val, (int, float)):
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        if isinstance(val, float) or abs(val) >= 1000:
                            cell.number_format = '#,##0.00'
                    elif isinstance(val, str) and val.startswith("="):
                        cell.font = bold_font
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="left", vertical="center")
            
            # Auto-fit column widths
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.value is not None:
                        val_str = str(cell.value)
                        max_len = max(max_len, len(val_str))
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
                
            # Optional Chart
            if s_info.get("create_chart") and len(rows) > 0 and len(headers) >= 2:
                try:
                    chart = BarChart()
                    chart.type = "col"
                    chart.style = 10
                    chart.title = s_info.get("chart_title", "Análisis Gráfico")
                    chart.y_axis.title = "Valores"
                    chart.x_axis.title = headers[0]
                    
                    data = Reference(ws, min_col=2, min_row=1, max_col=len(headers), max_row=len(rows)+1)
                    cats = Reference(ws, min_col=1, min_row=2, max_row=len(rows)+1)
                    chart.add_data(data, titles_from_data=True)
                    chart.set_categories(cats)
                    chart.width = 16
                    chart.height = 10
                    ws.add_chart(chart, f"A{len(rows) + 4}")
                except Exception:
                    pass
                    
        wb.save(full_path)
        return {
            "status": "success",
            "file_name": filename,
            "full_path": full_path,
            "message": f"Archivo Excel '{filename}' generado con éxito con diseño profesional y {len(sheets_data)} hojas."
        }

    @staticmethod
    def create_word(project_path: str, filename: str, title: str, subtitle: Optional[str], sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates a formatted Word document (.docx).
        sections is a list of dicts:
        [
            {
                "heading": "Resumen Ejecutivo",
                "level": 1, # 1 or 2
                "paragraphs": ["Texto párrafo 1...", "Texto párrafo 2..."],
                "bullet_points": ["Punto 1", "Punto 2"],
                "callout": "Nota importante o conclusión destacada...",
                "table": {
                    "headers": ["Col 1", "Col 2"],
                    "rows": [["A", "B"], ["C", "D"]]
                }
            }
        ]
        """
        if not filename.endswith(".docx"):
            filename += ".docx"
        full_path = os.path.join(project_path, filename)
        
        doc = docx.Document()
        
        # Page Margins
        for section in doc.sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)
            
        # Title
        title_p = doc.add_paragraph()
        title_p.paragraph_format.space_before = Pt(12)
        title_p.paragraph_format.space_after = Pt(4)
        title_run = title_p.add_run(title)
        title_run.font.name = "Segoe UI"
        title_run.font.size = Pt(24)
        title_run.font.bold = True
        title_run.font.color.rgb = RGBColor(30, 41, 59) # Deep slate
        
        if subtitle:
            sub_p = doc.add_paragraph()
            sub_p.paragraph_format.space_after = Pt(20)
            sub_run = sub_p.add_run(subtitle)
            sub_run.font.name = "Segoe UI"
            sub_run.font.size = Pt(13)
            sub_run.font.color.rgb = RGBColor(100, 116, 139) # Cool slate
            
        # Divider line
        p_div = doc.add_paragraph()
        p_div.paragraph_format.space_after = Pt(16)
        r_div = p_div.add_run("―" * 40)
        r_div.font.color.rgb = RGBColor(226, 232, 240)
        
        # Sections
        for sec in sections:
            heading_text = sec.get("heading")
            if heading_text:
                level = sec.get("level", 1)
                h_p = doc.add_paragraph()
                h_p.paragraph_format.space_before = Pt(14)
                h_p.paragraph_format.space_after = Pt(6)
                h_run = h_p.add_run(heading_text)
                h_run.font.name = "Segoe UI"
                h_run.font.bold = True
                if level == 1:
                    h_run.font.size = Pt(16)
                    h_run.font.color.rgb = RGBColor(37, 99, 235) # Vibrant Blue
                else:
                    h_run.font.size = Pt(13)
                    h_run.font.color.rgb = RGBColor(71, 85, 105)
            
            # Paragraphs
            for p_text in sec.get("paragraphs", []):
                p = doc.add_paragraph()
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.space_after = Pt(8)
                run = p.add_run(p_text)
                run.font.name = "Segoe UI"
                run.font.size = Pt(11)
                run.font.color.rgb = RGBColor(51, 65, 85)
                
            # Bullet points
            for bp in sec.get("bullet_points", []):
                bp_p = doc.add_paragraph(style='List Bullet')
                bp_p.paragraph_format.space_after = Pt(4)
                bp_p.paragraph_format.line_spacing = 1.15
                run = bp_p.add_run(bp)
                run.font.name = "Segoe UI"
                run.font.size = Pt(10.5)
                run.font.color.rgb = RGBColor(51, 65, 85)
                
            # Callout Box
            callout = sec.get("callout")
            if callout:
                tbl = doc.add_table(rows=1, cols=1)
                tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
                cell = tbl.cell(0, 0)
                cell.width = Inches(6.5)
                # Shading and left border
                shd = parse_xml(r'<w:shd {} w:fill="F1F5F9"/>'.format(nsdecls('w')))
                cell._tc.get_or_add_tcPr().append(shd)
                borders = parse_xml(
                    r'<w:tcBorders {}><w:left w:val="single" w:sz="24" w:space="0" w:color="2563EB"/>'
                    r'<w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/></w:tcBorders>'.format(nsdecls('w'))
                )
                cell._tc.get_or_add_tcPr().append(borders)
                cp = cell.paragraphs[0]
                cp.paragraph_format.space_before = Pt(8)
                cp.paragraph_format.space_after = Pt(8)
                c_run = cp.add_run(f"📌 {callout}")
                c_run.font.name = "Segoe UI"
                c_run.font.size = Pt(10.5)
                c_run.font.italic = True
                c_run.font.color.rgb = RGBColor(30, 41, 59)
                doc.add_paragraph().paragraph_format.space_after = Pt(6)
                
            # Table
            table_data = sec.get("table")
            if table_data and "headers" in table_data and "rows" in table_data:
                headers = table_data["headers"]
                rows = table_data["rows"]
                t = doc.add_table(rows=len(rows) + 1, cols=len(headers))
                t.alignment = WD_TABLE_ALIGNMENT.CENTER
                
                # Format headers
                hdr_cells = t.rows[0].cells
                for i, h_text in enumerate(headers):
                    hdr_cells[i].text = str(h_text)
                    shd = parse_xml(r'<w:shd {} w:fill="1E293B"/>'.format(nsdecls('w')))
                    hdr_cells[i]._tc.get_or_add_tcPr().append(shd)
                    p = hdr_cells[i].paragraphs[0]
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for r in p.runs:
                        r.font.name = "Segoe UI"
                        r.font.bold = True
                        r.font.size = Pt(10)
                        r.font.color.rgb = RGBColor(255, 255, 255)
                        
                # Format rows
                for r_idx, r_data in enumerate(rows):
                    row_cells = t.rows[r_idx + 1].cells
                    for c_idx, val in enumerate(r_data):
                        row_cells[c_idx].text = str(val)
                        if r_idx % 2 == 1:
                            shd = parse_xml(r'<w:shd {} w:fill="F8FAFC"/>'.format(nsdecls('w')))
                            row_cells[c_idx]._tc.get_or_add_tcPr().append(shd)
                        p = row_cells[c_idx].paragraphs[0]
                        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        for r in p.runs:
                            r.font.name = "Segoe UI"
                            r.font.size = Pt(9.5)
                            r.font.color.rgb = RGBColor(51, 65, 85)
                doc.add_paragraph().paragraph_format.space_after = Pt(10)
                
        doc.save(full_path)
        return {
            "status": "success",
            "file_name": filename,
            "full_path": full_path,
            "message": f"Documento Word '{filename}' generado con éxito con diseño ejecutivo."
        }

    @staticmethod
    def create_powerpoint(project_path: str, filename: str, title: str, subtitle: Optional[str], slides_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates a modern 16:9 widescreen presentation (.pptx).
        slides_data is a list of dicts:
        [
            {
                "title": "Oportunidades de Crecimiento",
                "bullets": ["Expansión digital...", "Alianzas estratégicas..."],
                "highlight": "Impacto estimado: +35% en retención.",
                "notes": "Puntos de orador..."
            }
        ]
        """
        if not filename.endswith(".pptx"):
            filename += ".pptx"
        full_path = os.path.join(project_path, filename)
        
        prs = Presentation()
        # Set to 16:9 widescreen
        prs.slide_width = PptxInches(13.333)
        prs.slide_height = PptxInches(7.5)
        
        blank_slide_layout = prs.slide_layouts[6] # Blank
        
        # Colors: Slate & Modern Blue
        bg_dark = PptxRGBColor(15, 23, 42) # Slate 900
        text_white = PptxRGBColor(248, 250, 252)
        text_muted = PptxRGBColor(148, 163, 184)
        accent_blue = PptxRGBColor(59, 130, 246) # Blue 500
        card_bg = PptxRGBColor(30, 41, 59) # Slate 800
        
        # Slide 1: Cover Slide
        cover_slide = prs.slides.add_slide(blank_slide_layout)
        # Background
        bg_shape = cover_slide.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height) # 1 = msoShapeRectangle
        bg_shape.fill.solid()
        bg_shape.fill.fore_color.rgb = bg_dark
        bg_shape.line.fill.background()
        
        # Title text box
        tb = cover_slide.shapes.add_textbox(PptxInches(1.5), PptxInches(2.5), PptxInches(10.33), PptxInches(2.5))
        tf = tb.text_frame
        tf.word_wrap = True
        
        p_title = tf.paragraphs[0]
        p_title.text = title
        p_title.font.name = "Segoe UI"
        p_title.font.size = PptxPt(44)
        p_title.font.bold = True
        p_title.font.color.rgb = text_white
        
        if subtitle:
            p_sub = tf.add_paragraph()
            p_sub.text = subtitle
            p_sub.font.name = "Segoe UI"
            p_sub.font.size = PptxPt(22)
            p_sub.font.color.rgb = accent_blue
            p_sub.space_before = PptxPt(16)
            
        # Content Slides
        for s_idx, s_info in enumerate(slides_data, start=2):
            slide = prs.slides.add_slide(blank_slide_layout)
            
            # Dark Background
            bg = slide.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
            bg.fill.solid()
            bg.fill.fore_color.rgb = bg_dark
            bg.line.fill.background()
            
            # Header Title
            tb_hdr = slide.shapes.add_textbox(PptxInches(1.0), PptxInches(0.8), PptxInches(11.33), PptxInches(1.0))
            tf_hdr = tb_hdr.text_frame
            tf_hdr.word_wrap = True
            p_h = tf_hdr.paragraphs[0]
            p_h.text = s_info.get("title", f"Sección {s_idx - 1}")
            p_h.font.name = "Segoe UI"
            p_h.font.size = PptxPt(30)
            p_h.font.bold = True
            p_h.font.color.rgb = text_white
            
            # Accent bar under title
            bar = slide.shapes.add_shape(1, PptxInches(1.0), PptxInches(1.8), PptxInches(1.5), PptxInches(0.06))
            bar.fill.solid()
            bar.fill.fore_color.rgb = accent_blue
            bar.line.fill.background()
            
            # Content Container (Card)
            card = slide.shapes.add_shape(1, PptxInches(1.0), PptxInches(2.2), PptxInches(11.33), PptxInches(4.4))
            card.fill.solid()
            card.fill.fore_color.rgb = card_bg
            card.line.fill.background()
            
            # Bullets text inside card
            tb_body = slide.shapes.add_textbox(PptxInches(1.4), PptxInches(2.5), PptxInches(10.5), PptxInches(3.8))
            tf_body = tb_body.text_frame
            tf_body.word_wrap = True
            
            bullets = s_info.get("bullets", [])
            for b_idx, bullet in enumerate(bullets):
                p = tf_body.paragraphs[0] if b_idx == 0 else tf_body.add_paragraph()
                p.text = f"•  {bullet}"
                p.font.name = "Segoe UI"
                p.font.size = PptxPt(20)
                p.font.color.rgb = text_white
                p.space_after = PptxPt(16)
                
            highlight = s_info.get("highlight")
            if highlight:
                p_hl = tf_body.add_paragraph()
                p_hl.text = f"💡 {highlight}"
                p_hl.font.name = "Segoe UI"
                p_hl.font.size = PptxPt(18)
                p_hl.font.bold = True
                p_hl.font.color.rgb = accent_blue
                p_hl.space_before = PptxPt(14)
                
        prs.save(full_path)
        return {
            "status": "success",
            "file_name": filename,
            "full_path": full_path,
            "message": f"Presentación PowerPoint '{filename}' generada con éxito con {len(slides_data) + 1} diapositivas en formato 16:9."
        }
