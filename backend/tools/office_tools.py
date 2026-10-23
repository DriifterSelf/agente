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
            import docx
            doc = docx.Document()
            doc.add_heading(title, 0)
            for sec in sections:
                if isinstance(sec, dict):
                    h = sec.get("heading")
                    if h:
                        doc.add_heading(h, level=sec.get("level", 1))
                    b = sec.get("body")
                    if b:
                        doc.add_paragraph(b)
                elif isinstance(sec, str):
                    doc.add_paragraph(sec)
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
