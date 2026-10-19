import os
import re
import zipfile
import json
from typing import List, Dict, Any, Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from pptx import Presentation
from pptx.util import Inches as PptxInches, Pt as PptxPt
from pptx.dml.color import RGBColor as PptxRGBColor

class OfficeTools:
    @staticmethod
    def sanitize_filename(filename: str, default_name: str = "archivo", expected_ext: str = "") -> str:
        """Sanitizes filename against illegal Windows characters and ensures proper extension."""
        if not filename or not str(filename).strip():
            filename = default_name
        # Strip illegal Windows characters: < > : " / \ | ? * and ASCII control chars
        clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(filename)).strip('. ')
        if not clean:
            clean = default_name
        if expected_ext and not clean.lower().endswith(expected_ext.lower()):
            clean += expected_ext
        return clean

    @staticmethod
    def create_excel(project_path: str, filename: str, sheets_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generates a professionally formatted Excel spreadsheet (.xlsx)."""
        filename = OfficeTools.sanitize_filename(filename, "Libro1", ".xlsx")
        full_path = os.path.join(project_path, filename)
        
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        
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
            
            for col_idx, header in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col_idx, value=str(header))
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = thin_border
            ws.row_dimensions[1].height = 28
            
            for r_idx, row in enumerate(rows, start=2):
                ws.row_dimensions[r_idx].height = 22
                for c_idx, val in enumerate(row, start=1):
                    cell = ws.cell(row=r_idx, column=c_idx, value=val)
                    cell.font = regular_font
                    cell.border = thin_border
                    if r_idx % 2 == 1:
                        cell.fill = alt_row_fill
                    if isinstance(val, (int, float)):
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        if isinstance(val, float) or abs(val) >= 1000:
                            cell.number_format = '#,##0.00'
                    elif isinstance(val, str) and val.startswith("="):
                        cell.font = bold_font
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="left", vertical="center")
            
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.value is not None:
                        max_len = max(max_len, len(str(cell.value)))
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
                
            if s_info.get("create_chart") and len(rows) > 0 and len(headers) >= 2:
                try:
                    chart = BarChart()
                    chart.type = "col"
                    chart.style = 10
                    chart.title = s_info.get("chart_title", "Análisis Gráfico")
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
            "message": f"Archivo Excel '{filename}' generado con éxito."
        }

    @staticmethod
    def create_word(project_path: str, filename: str, title: str, subtitle: Optional[str], sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generates a formatted Word document (.docx)."""
        filename = OfficeTools.sanitize_filename(filename, "Documento", ".docx")
        full_path = os.path.join(project_path, filename)
        
        doc = docx.Document()
        for section in doc.sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)
            
        title_p = doc.add_paragraph()
        title_p.paragraph_format.space_before = Pt(12)
        title_p.paragraph_format.space_after = Pt(4)
        title_run = title_p.add_run(title)
        title_run.font.name = "Segoe UI"
        title_run.font.size = Pt(24)
        title_run.font.bold = True
        title_run.font.color.rgb = RGBColor(30, 41, 59)
        
        if subtitle:
            sub_p = doc.add_paragraph()
            sub_p.paragraph_format.space_after = Pt(20)
            sub_run = sub_p.add_run(subtitle)
            sub_run.font.name = "Segoe UI"
            sub_run.font.size = Pt(13)
            sub_run.font.color.rgb = RGBColor(100, 116, 139)
            
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
                h_run.font.size = Pt(16 if level == 1 else 13)
                h_run.font.color.rgb = RGBColor(37, 99, 235) if level == 1 else RGBColor(71, 85, 105)
            
            for p_text in sec.get("paragraphs", []):
                p = doc.add_paragraph()
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.space_after = Pt(8)
                run = p.add_run(p_text)
                run.font.name = "Segoe UI"
                run.font.size = Pt(11)
                run.font.color.rgb = RGBColor(51, 65, 85)
                
            for bp in sec.get("bullet_points", []):
                bp_p = doc.add_paragraph(style='List Bullet')
                bp_p.paragraph_format.space_after = Pt(4)
                run = bp_p.add_run(bp)
                run.font.name = "Segoe UI"
                run.font.size = Pt(10.5)
                run.font.color.rgb = RGBColor(51, 65, 85)
                
            callout = sec.get("callout")
            if callout:
                tbl = doc.add_table(rows=1, cols=1)
                tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
                cell = tbl.cell(0, 0)
                cell.width = Inches(6.5)
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
                
            table_data = sec.get("table")
            if table_data and "headers" in table_data and "rows" in table_data:
                headers = table_data["headers"]
                rows = table_data["rows"]
                t = doc.add_table(rows=len(rows) + 1, cols=len(headers))
                t.alignment = WD_TABLE_ALIGNMENT.CENTER
                
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
            "message": f"Documento Word '{filename}' generado con éxito."
        }

    @staticmethod
    def create_powerpoint(project_path: str, filename: str, title: str, subtitle: Optional[str], slides_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generates a modern 16:9 widescreen presentation (.pptx)."""
        filename = OfficeTools.sanitize_filename(filename, "Presentacion", ".pptx")
        full_path = os.path.join(project_path, filename)
        
        prs = Presentation()
        prs.slide_width = PptxInches(13.333)
        prs.slide_height = PptxInches(7.5)
        
        blank_layout = prs.slide_layouts[6]
        bg_dark = PptxRGBColor(15, 23, 42)
        text_white = PptxRGBColor(248, 250, 252)
        accent_blue = PptxRGBColor(59, 130, 246)
        card_bg = PptxRGBColor(30, 41, 59)
        
        cover = prs.slides.add_slide(blank_layout)
        bg = cover.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = bg_dark
        bg.line.fill.background()
        
        tb = cover.shapes.add_textbox(PptxInches(1.5), PptxInches(2.5), PptxInches(10.33), PptxInches(2.5))
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
            
        for s_idx, s_info in enumerate(slides_data, start=2):
            slide = prs.slides.add_slide(blank_layout)
            bg = slide.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
            bg.fill.solid()
            bg.fill.fore_color.rgb = bg_dark
            bg.line.fill.background()
            
            tb_hdr = slide.shapes.add_textbox(PptxInches(1.0), PptxInches(0.8), PptxInches(11.33), PptxInches(1.0))
            tf_hdr = tb_hdr.text_frame
            tf_hdr.word_wrap = True
            p_h = tf_hdr.paragraphs[0]
            p_h.text = s_info.get("title", f"Diapositiva {s_idx - 1}")
            p_h.font.name = "Segoe UI"
            p_h.font.size = PptxPt(30)
            p_h.font.bold = True
            p_h.font.color.rgb = text_white
            
            bar = slide.shapes.add_shape(1, PptxInches(1.0), PptxInches(1.8), PptxInches(1.5), PptxInches(0.06))
            bar.fill.solid()
            bar.fill.fore_color.rgb = accent_blue
            bar.line.fill.background()
            
            card = slide.shapes.add_shape(1, PptxInches(1.0), PptxInches(2.2), PptxInches(11.33), PptxInches(4.4))
            card.fill.solid()
            card.fill.fore_color.rgb = card_bg
            card.line.fill.background()
            
            tb_body = slide.shapes.add_textbox(PptxInches(1.4), PptxInches(2.5), PptxInches(10.5), PptxInches(3.8))
            tf_body = tb_body.text_frame
            tf_body.word_wrap = True
            
            for b_idx, bullet in enumerate(s_info.get("bullets", [])):
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
            "message": f"Presentación PowerPoint '{filename}' generada con éxito."
        }

    @staticmethod
    def create_pdf(project_path: str, filename: str, title: str, subtitle: Optional[str], content_paragraphs: List[str], tables: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Generates a polished PDF document directly with ReportLab."""
        filename = OfficeTools.sanitize_filename(filename, "Documento", ".pdf")
        full_path = os.path.join(project_path, filename)
        
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        doc = SimpleDocTemplate(full_path, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=24,
            leading=28,
            textColor=colors.HexColor('#1E293B'),
            spaceAfter=8
        )
        sub_style = ParagraphStyle(
            'CustomSub',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#64748B'),
            spaceAfter=20
        )
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor('#334155'),
            spaceAfter=10
        )
        table_cell_style = ParagraphStyle(
            'TableCellStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#334155')
        )
        table_hdr_style = ParagraphStyle(
            'TableHdrStyle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9.5,
            leading=13,
            textColor=colors.white
        )
        
        story = []
        story.append(Paragraph(title, title_style))
        if subtitle:
            story.append(Paragraph(subtitle, sub_style))
            
        for p in content_paragraphs:
            story.append(Paragraph(p, body_style))
            story.append(Spacer(1, 6))
            
        if tables:
            for tbl in tables:
                headers = tbl.get("headers", [])
                rows = tbl.get("rows", [])
                formatted_headers = [Paragraph(str(h), table_hdr_style) for h in headers]
                formatted_rows = [
                    [Paragraph(str(val), table_cell_style) for val in row]
                    for row in rows
                ]
                table_data = [formatted_headers] + formatted_rows
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
                ]))
                story.append(Spacer(1, 10))
                story.append(t)
                story.append(Spacer(1, 14))
                
        doc.build(story)
        return {
            "status": "success",
            "file_name": filename,
            "full_path": full_path,
            "message": f"Documento PDF '{filename}' generado con éxito."
        }

    @staticmethod
    def create_chart_image(project_path: str, filename: str, chart_type: str, title: str, labels: List[str], values: List[float], x_label: str = "", y_label: str = "") -> Dict[str, Any]:
        """Generates a high-resolution PNG chart image using Matplotlib."""
        filename = OfficeTools.sanitize_filename(filename, "grafico", ".png")
        full_path = os.path.join(project_path, filename)
        
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        plt.figure(figsize=(9, 5.5), facecolor='#0F172A')
        ax = plt.subplot(111)
        ax.set_facecolor('#1E293B')
        
        colors = ['#3B82F6', '#10B981', '#F59E0B', '#EC4899', '#8B5CF6', '#06B6D4']
        
        if chart_type == "bar":
            bars = ax.bar(labels, values, color=colors[:len(labels)], edgecolor='#334155', width=0.55)
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height + (height * 0.02),
                        f'{height:,.1f}', ha='center', va='bottom', color='#F8FAFC', fontsize=9, fontweight='bold')
        elif chart_type == "line":
            ax.plot(labels, values, marker='o', linewidth=2.5, color='#3B82F6', markersize=6, markerfacecolor='#60A5FA')
        elif chart_type == "pie":
            plt.figure(figsize=(7, 7), facecolor='#0F172A')
            plt.pie(values, labels=labels, autopct='%1.1f%%', colors=colors[:len(labels)], textprops={'color': '#F8FAFC', 'fontsize': 10})
            plt.title(title, color='#F8FAFC', fontsize=14, fontweight='bold', pad=15)
            plt.savefig(full_path, dpi=200, bbox_inches='tight', facecolor='#0F172A')
            plt.close()
            return {"status": "success", "file_name": filename, "full_path": full_path, "message": f"Gráfico circular '{filename}' generado con éxito."}
            
        ax.set_title(title, color='#F8FAFC', fontsize=14, fontweight='bold', pad=15)
        if x_label: ax.set_xlabel(x_label, color='#94A3B8', fontsize=10)
        if y_label: ax.set_ylabel(y_label, color='#94A3B8', fontsize=10)
        ax.tick_params(colors='#94A3B8', labelsize=9)
        for spine in ax.spines.values(): spine.set_color('#334155')
        ax.grid(axis='y', linestyle='--', alpha=0.2, color='#94A3B8')
        
        plt.tight_layout()
        plt.savefig(full_path, dpi=200, bbox_inches='tight', facecolor='#0F172A')
        plt.close()
        
        return {
            "status": "success",
            "file_name": filename,
            "full_path": full_path,
            "message": f"Gráfico de imagen '{filename}' generado con éxito."
        }

    @staticmethod
    def create_file(project_path: str, filename: str, content: str) -> Dict[str, Any]:
        """Creates any text or formatted data file (.json, .csv, .html, .xml, .py, .sql, .md, .txt, .yaml)."""
        filename = OfficeTools.sanitize_filename(filename, "archivo.txt")
        full_path = os.path.join(project_path, filename)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {
            "status": "success",
            "file_name": filename,
            "full_path": full_path,
            "message": f"Archivo '{filename}' creado con éxito."
        }

    @staticmethod
    def create_zip(project_path: str, archive_name: str, files_to_include: List[str]) -> Dict[str, Any]:
        """Packages files into a .zip archive. If files_to_include is empty, packages all files in project."""
        archive_name = OfficeTools.sanitize_filename(archive_name, "entrega", ".zip")
        full_path = os.path.join(project_path, archive_name)
        
        target_files = list(files_to_include or [])
        if not target_files and os.path.exists(project_path):
            target_files = [
                f.name for f in os.scandir(project_path)
                if f.is_file() and not f.name.lower().endswith(".zip") and f.name != archive_name
            ]
        
        with zipfile.ZipFile(full_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f_name in target_files:
                f_path = os.path.join(project_path, f_name)
                if os.path.exists(f_path):
                    z.write(f_path, arcname=f_name)
                    
        return {
            "status": "success",
            "file_name": archive_name,
            "full_path": full_path,
            "message": f"Archivo comprimido '{archive_name}' creado con {len(target_files)} archivos."
        }
