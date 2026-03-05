from fpdf import FPDF
from datetime import datetime

class MeloReport(FPDF):
    def header(self):
        # Logo
        self.set_font('helvetica', 'BI', 20)
        self.set_text_color(4, 61, 174) # Primary color #043dae
        self.cell(40, 10, 'Melo ', 0, 0, 'L')
        self.set_font('helvetica', 'B', 20)
        self.set_text_color(30, 41, 59) # Slate-900
        self.cell(40, 10, 'Finance', 0, 1, 'L')
        self.set_font('helvetica', 'B', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 5, 'REPORTE FINANCIERO PROFESIONAL', 0, 1, 'L')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f'Pagina {self.page_no()} | Melo Finance - Gestion Inteligente de Prestamos', 0, 0, 'C')

    def watermark(self):
        self.set_font('helvetica', 'B', 50)
        self.set_text_color(4, 61, 174)
        self.set_alpha(0.1)
        with self.rotation(45, 105, 148):
            self.text(40, 190, "MELO FINANCE SYSTEM")
        self.set_alpha(1)

def generate_loan_report(user_name, loans_data, total_stats):
    pdf = MeloReport()
    pdf.add_page()
    pdf.watermark()
    
    # Title
    pdf.set_font('helvetica', 'B', 16)
    pdf.set_text_color(15, 22, 35)
    pdf.cell(0, 10, f'Resumen de Cartera: {user_name}', 0, 1, 'L')
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 10, f'Fecha de emision: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'L')
    pdf.ln(5)

    # Stats Boxes
    pdf.set_fill_color(245, 246, 248)
    pdf.rect(10, 50, 60, 25, 'F')
    pdf.set_xy(10, 52)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(100)
    pdf.cell(60, 5, 'DISPONIBLE USD', 0, 1, 'C')
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(4, 61, 174)
    pdf.cell(60, 10, f"${total_stats['usd']}", 0, 1, 'C')

    pdf.rect(75, 50, 60, 25, 'F')
    pdf.set_xy(75, 52)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(100)
    pdf.cell(60, 5, 'DISPONIBLE VES', 0, 1, 'C')
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(4, 61, 174)
    pdf.cell(60, 10, f"Bs.{total_stats['ves']}", 0, 1, 'C')

    pdf.rect(140, 50, 60, 25, 'F')
    pdf.set_xy(140, 52)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(100)
    pdf.cell(60, 5, 'PRESTAMOS ACTIVOS', 0, 1, 'C')
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(4, 61, 174)
    pdf.cell(60, 10, f"{total_stats['active_count']}", 0, 1, 'C')

    pdf.ln(20)

    # Table Header
    pdf.set_fill_color(4, 61, 174)
    pdf.set_text_color(255)
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(60, 10, 'Cliente', 1, 0, 'C', True)
    pdf.cell(40, 10, 'Monto Original', 1, 0, 'C', True)
    pdf.cell(30, 10, 'Moneda', 1, 0, 'C', True)
    pdf.cell(30, 10, 'Estatus', 1, 0, 'C', True)
    pdf.cell(30, 10, 'Vencimiento', 1, 1, 'C', True)

    # Table Body
    pdf.set_text_color(30)
    pdf.set_font('helvetica', '', 9)
    for loan in loans_data:
        pdf.cell(60, 8, loan['cliente'], 1, 0, 'L')
        pdf.cell(40, 8, f"{loan['monto']}", 1, 0, 'R')
        pdf.cell(30, 8, loan['moneda'], 1, 0, 'C')
        pdf.cell(30, 8, loan['estatus'], 1, 0, 'C')
        pdf.cell(30, 8, loan['vencimiento'], 1, 1, 'C')

    return pdf.output()
