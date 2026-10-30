import os

class OfficeTools:
    @staticmethod
    def create_excel(project_path: str, filename: str, sheets_data: dict):
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            # remove default sheet
            default_sheet = wb.active
            first = True
            for sheet_name, rows in sheets_data.items():
                if first:
                    ws = default_sheet
                    ws.title = sheet_name[:31]
                    first = False
                else:
                    ws = wb.create_sheet(title=sheet_name[:31])
                for r_idx, row in enumerate(rows, 1):
                    for c_idx, val in enumerate(row, 1):
                        ws.cell(row=r_idx, column=c_idx, value=val)
            target = os.path.join(project_path, filename)
            wb.save(target)
            return {"status": "success", "file": target}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    def create_word(project_path: str, filename: str, title: str, sections: list):
        try:
            import re
            import docx
            from docx.shared import Pt, Inches
            from docx.enum.text import WD_ALIGN_PARAGRAPH

            doc = docx.Document()
            for s in doc.sections:
                s.top_margin = Inches(1.0)
                s.bottom_margin = Inches(1.0)
                s.left_margin = Inches(1.0)
                s.right_margin = Inches(1.0)

            doc.add_heading(title, 0)
            for sec in sections:
                if isinstance(sec, dict):
                    h = sec.get("heading")
                    if h:
                        doc.add_heading(h, level=sec.get("level", 1))
                    b = sec.get("body", "")
                    if b:
                        for para_block in [p.strip() for p in re.split(r"\n\s*\n", str(b)) if p.strip()]:
                            p = doc.add_paragraph()
                            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                            p.paragraph_format.line_spacing = 1.35
                            p.paragraph_format.space_after = Pt(8)
                            tokens = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", para_block)
                            for tok in tokens:
                                if not tok:
                                    continue
                                if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
                                    r = p.add_run(tok[2:-2])
                                    r.bold = True
                                elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
                                    r = p.add_run(tok[1:-1])
                                    r.italic = True
                                else:
                                    p.add_run(tok)
                elif isinstance(sec, str) and sec.strip():
                    p = doc.add_paragraph(sec.strip())
                    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                    p.paragraph_format.line_spacing = 1.35
            target = os.path.join(project_path, filename)
            doc.save(target)
            return {"status": "success", "file": target}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    def create_powerpoint(project_path: str, filename: str, title: str, slides: list):
        try:
            from pptx import Presentation
            prs = Presentation()
            title_layout = prs.slide_layouts[0]
            title_slide = prs.slides.add_slide(title_layout)
            title_slide.shapes.title.text = title

            bullet_layout = prs.slide_layouts[1]
            for s in slides:
                slide = prs.slides.add_slide(bullet_layout)
                slide.shapes.title.text = s.get("title", "")
                tf = slide.placeholders[1].text_frame
                bullets = s.get("bullets", [])
                for idx, b in enumerate(bullets):
                    if idx == 0:
                        tf.text = b
                    else:
                        p = tf.add_paragraph()
                        p.text = b
            target = os.path.join(project_path, filename)
            prs.save(target)
            return {"status": "success", "file": target}
        except Exception as e:
            return {"status": "error", "error": str(e)}
