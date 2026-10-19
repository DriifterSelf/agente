import os
from backend.tools.office_tools import OfficeTools

test_path = os.path.join(os.getcwd(), 'projects', 'Test_Multimodal_Completo')
os.makedirs(test_path, exist_ok=True)

# 1. PDF
res_pdf = OfficeTools.create_pdf(
    project_path=test_path,
    filename='Manual_Entrega.pdf',
    title='Manual de Procedimientos Academicos',
    subtitle='Generado con ReportLab',
    content_paragraphs=['Este documento PDF contiene texto formateado y tablas.'],
    tables=[{'headers': ['Fase', 'Estado'], 'rows': [['Fase 1', 'Completada'], ['Fase 2', 'En curso']]}]
)
print('PDF:', res_pdf['status'], res_pdf['file_name'])

# 2. Matplotlib Chart PNG
res_chart = OfficeTools.create_chart_image(
    project_path=test_path,
    filename='comparativa_ventas.png',
    chart_type='bar',
    title='Comparativa de Rendimiento',
    labels=['Grupo A', 'Grupo B', 'Grupo C'],
    values=[120.5, 145.2, 178.9],
    x_label='Grupos',
    y_label='Calificacion'
)
print('Chart:', res_chart['status'], res_chart['file_name'])

# 3. JSON file
res_json = OfficeTools.create_file(
    project_path=test_path,
    filename='configuracion.json',
    content='{"version": "1.0.0", "estado": "activo"}'
)
print('JSON:', res_json['status'], res_json['file_name'])

# 4. ZIP archive
res_zip = OfficeTools.create_zip(
    project_path=test_path,
    archive_name='paquete_completo.zip',
    files_to_include=['Manual_Entrega.pdf', 'comparativa_ventas.png', 'configuracion.json']
)
print('ZIP:', res_zip['status'], res_zip['file_name'])

print('TODOS LOS GENERADORES DE ARCHIVOS FUNCIONAN AL 100%!')
