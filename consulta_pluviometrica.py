import csv
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

API_URL = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos"

BG = "#F3F6FA"
NAVY = "#12304A"
BLUE = "#176B87"
GREEN = "#2D9C75"
TEXT = "#263746"
MUTED = "#6B7C8F"
WHITE = "#FFFFFF"

def local_name(tag):
    return tag.rsplit("}", 1)[-1].split(":")[-1].strip().lower()

def parse_api_xml(xml_text):
    """Interpreta o DataTable XML da ANA, inclusive quando o resultado contém XML escapado."""
    root = ET.fromstring(xml_text)

    # Algumas respostas da API retornam o conteúdo interno como texto XML escapado.
    nested_texts = []
    for el in root.iter():
        if el.text and el.text.strip().startswith("<"):
            nested_texts.append(el.text.strip())
    for nested in nested_texts:
        try:
            nested_root = ET.fromstring(nested)
            root = nested_root
            break
        except ET.ParseError:
            continue

    known = {
        "codestacao", "datahora", "chuva", "precipitacao", "precipitação",
        "precipitacaomm", "chuva_mm", "valorchuva", "nivel", "vazao"
    }
    records = []
    for element in root.iter():
        row = {}
        for child in list(element):
            name = local_name(child.tag)
            if name in known:
                row[name] = (child.text or "").strip()
        if row and any(k in row for k in ("datahora", "chuva", "precipitacao", "precipitação",
                                           "precipitacaomm", "chuva_mm", "valorchuva")):
            records.append(row)

    unique, seen = [], set()
    for row in records:
        key = tuple(sorted(row.items()))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique

def value_of(row, *keys):
    for key in keys:
        value = row.get(key.lower())
        if value not in (None, ""):
            return value
    return ""

def fetch_data(station, start_date, end_date):
    params = urllib.parse.urlencode({
        "codEstacao": station,
        "dataInicio": start_date,
        "dataFim": end_date
    })
    request = urllib.request.Request(
        f"{API_URL}?{params}",
        headers={"User-Agent": "ConsultaPluviometrica/1.0", "Accept": "application/xml"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
    return parse_api_xml(body)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PluvioANA | Consulta de precipitação")
        self.geometry("1100x720")
        self.minsize(850, 600)
        self.configure(bg=BG)
        self.records = []
        self.setup_style()
        self.build_screen()

    def setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=WHITE, foreground=TEXT,
                        rowheight=34, fieldbackground=WHITE, borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#E8EEF4", foreground=NAVY,
                        font=("Segoe UI", 10, "bold"), padding=(10, 11), relief="flat")
        style.map("Treeview", background=[("selected", "#D8EAF2")],
                  foreground=[("selected", NAVY)])
        style.configure("Vertical.TScrollbar", background="#DCE5EC", troughcolor=WHITE,
                        bordercolor=WHITE, arrowsize=12)

    def build_screen(self):
        # Cabeçalho
        header = tk.Frame(self, bg=NAVY, height=112)
        header.pack(fill="x")
        header.pack_propagate(False)
        logo = tk.Label(header, text="☔", font=("DejaVu Sans", 28), bg=NAVY, fg=WHITE)
        logo.pack(side="left", padx=(28, 14), pady=20)
        title_box = tk.Frame(header, bg=NAVY)
        title_box.pack(side="left", pady=20)
        tk.Label(title_box, text="PluvioANA", font=("Segoe UI", 22, "bold"),
                 bg=NAVY, fg=WHITE).pack(anchor="w")
        tk.Label(title_box, text="CONSULTA DE DADOS PLUVIOMÉTRICOS",
                 font=("Segoe UI", 9, "bold"), bg=NAVY, fg="#BBD5E3").pack(anchor="w", pady=(2, 0))
        tk.Label(header, text="DADOS HIDROMETEOROLÓGICOS  •  ANA",
                 font=("Segoe UI", 9, "bold"), bg=NAVY, fg="#D6E5EC").pack(side="right", padx=28)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=28, pady=22)

        tk.Label(body, text="Painel de consulta", font=("Segoe UI", 19, "bold"),
                 bg=BG, fg=NAVY).pack(anchor="w")
        tk.Label(body, text="Selecione uma estação e um intervalo de datas para consultar os registros de chuva.",
                 font=("Segoe UI", 10), bg=BG, fg=MUTED).pack(anchor="w", pady=(4, 18))

        # Cartão de filtros
        filter_card = tk.Frame(body, bg=WHITE, highlightbackground="#DDE5EC", highlightthickness=1)
        filter_card.pack(fill="x")
        tk.Label(filter_card, text="PARÂMETROS DA CONSULTA", font=("Segoe UI", 9, "bold"),
                 bg=WHITE, fg=BLUE).grid(row=0, column=0, columnspan=4, sticky="w", padx=18, pady=(16, 12))

        self.station = self.make_field(filter_card, "Código da estação", 0, 1, "Ex.: 12345678")
        self.start = self.make_field(filter_card, "Data inicial", 1, 1, "dd/mm/aaaa")
        self.end = self.make_field(filter_card, "Data final", 2, 1, "dd/mm/aaaa")
        self.start.insert(0, "01/01/2026")
        self.end.insert(0, datetime.now().strftime("%d/%m/%Y"))

        self.search_btn = tk.Button(filter_card, text="⌕  Consultar dados", command=self.consult,
                                    font=("Segoe UI", 10, "bold"), bg=BLUE, fg=WHITE,
                                    activebackground="#0F5872", activeforeground=WHITE,
                                    relief="flat", bd=0, cursor="hand2", padx=18, pady=11)
        self.search_btn.grid(row=1, column=3, rowspan=2, padx=(10, 18), pady=(4, 12), sticky="e")
        filter_card.columnconfigure(0, weight=1)
        filter_card.columnconfigure(1, weight=1)
        filter_card.columnconfigure(2, weight=1)

        # Cabeçalho dos resultados
        results_top = tk.Frame(body, bg=BG)
        results_top.pack(fill="x", pady=(22, 10))
        tk.Label(results_top, text="Registros encontrados", font=("Segoe UI", 15, "bold"),
                 bg=BG, fg=NAVY).pack(side="left")
        self.count_label = tk.Label(results_top, text="0 registros", font=("Segoe UI", 9, "bold"),
                                    bg="#E2F3EC", fg="#217653", padx=10, pady=5)
        self.count_label.pack(side="left", padx=12)
        self.export_btn = tk.Button(results_top, text="↓  Exportar CSV", command=self.export_csv,
                                    font=("Segoe UI", 10, "bold"), bg=GREEN, fg=WHITE,
                                    activebackground="#238260", activeforeground=WHITE,
                                    relief="flat", bd=0, cursor="hand2", padx=16, pady=9,
                                    state="disabled")
        self.export_btn.pack(side="right")

        # Tabela
        table_card = tk.Frame(body, bg=WHITE, highlightbackground="#DDE5EC", highlightthickness=1)
        table_card.pack(fill="both", expand=True)
        cols = ("station", "date", "time", "rain")
        self.table = ttk.Treeview(table_card, columns=cols, show="headings")
        self.table.heading("station", text="CÓDIGO DA ESTAÇÃO")
        self.table.heading("date", text="DATA")
        self.table.heading("time", text="HORA")
        self.table.heading("rain", text="PRECIPITAÇÃO (MM)")
        self.table.column("station", width=210, anchor="center")
        self.table.column("date", width=190, anchor="center")
        self.table.column("time", width=180, anchor="center")
        self.table.column("rain", width=220, anchor="center")
        scroll = ttk.Scrollbar(table_card, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)

        # Rodapé/status
        footer = tk.Frame(body, bg=BG)
        footer.pack(fill="x", pady=(10, 0))
        self.status = tk.StringVar(value="Pronto para consultar. Os resultados serão exibidos nesta tabela.")
        tk.Label(footer, textvariable=self.status, font=("Segoe UI", 9),
                 bg=BG, fg=MUTED, wraplength=750, justify="left").pack(side="left")
        tk.Label(footer, text="Fonte: Serviço ANA", font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=MUTED).pack(side="right")

    def make_field(self, parent, label, col, row, placeholder):
        box = tk.Frame(parent, bg=WHITE)
        box.grid(row=row, column=col, sticky="ew", padx=(18 if col == 0 else 8, 8), pady=(0, 12))
        tk.Label(box, text=label, font=("Segoe UI", 9, "bold"), bg=WHITE, fg=TEXT).pack(anchor="w", pady=(0, 6))
        entry = tk.Entry(box, font=("Segoe UI", 10), bg="#F8FAFC", fg=TEXT,
                         insertbackground=TEXT, relief="flat", highlightthickness=1,
                         highlightbackground="#D4DEE7", highlightcolor=BLUE)
        entry.pack(fill="x", ipady=9, padx=1, pady=1)
        return entry

    def consult(self):
        station, start, end = self.station.get().strip(), self.start.get().strip(), self.end.get().strip()
        if not station.isdigit():
            messagebox.showwarning("Campo inválido", "Informe o código numérico da estação.")
            return
        try:
            start_dt = datetime.strptime(start, "%d/%m/%Y")
            end_dt = datetime.strptime(end, "%d/%m/%Y")
        except ValueError:
            messagebox.showwarning("Data inválida", "Informe as datas no formato dd/mm/aaaa.")
            return
        if start_dt > end_dt:
            messagebox.showwarning("Período inválido", "A data inicial deve ser anterior ou igual à data final.")
            return
        self.search_btn.configure(state="disabled", text="Consultando…")
        self.export_btn.configure(state="disabled")
        self.status.set("Conectando ao serviço da ANA…")
        threading.Thread(target=self._fetch, args=(station, start, end), daemon=True).start()

    def _fetch(self, station, start, end):
        try:
            data = fetch_data(station, start, end)
            self.after(0, lambda: self.show_results(data, station))
        except Exception as exc:
            self.after(0, lambda: self.show_error(str(exc)))

    def show_results(self, rows, requested_station):
        self.search_btn.configure(state="normal", text="⌕  Consultar dados")
        for item in self.table.get_children():
            self.table.delete(item)
        self.records = []
        for row in rows:
            station = value_of(row, "codestacao") or requested_station
            date_time = value_of(row, "datahora")
            rain = value_of(row, "chuva", "precipitacao", "precipitação", "precipitacaomm", "chuva_mm", "valorchuva")
            if not date_time and not rain:
                continue
            date_part, time_part = date_time, ""
            for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    parsed = datetime.strptime(date_time, fmt)
                    date_part, time_part = parsed.strftime("%d/%m/%Y"), parsed.strftime("%H:%M:%S")
                    break
                except ValueError:
                    pass
            rain = rain or "não informado"
            values = (station, date_part, time_part, rain)
            self.table.insert("", "end", values=values)
            self.records.append({
                "Código da estação": station, "Data": date_part,
                "Hora": time_part, "Precipitação (mm)": rain
            })
        self.count_label.configure(text=f"{len(self.records)} registro(s)")
        if self.records:
            self.status.set("Consulta concluída. Você pode exportar os registros para CSV.")
            self.export_btn.configure(state="normal")
        else:
            self.status.set("Consulta concluída, mas nenhum registro reconhecível foi retornado.")
            messagebox.showinfo("Sem resultados", "A API não retornou registros de precipitação reconhecíveis para esse período.")

    def show_error(self, error):
        self.search_btn.configure(state="normal", text="⌕  Consultar dados")
        self.status.set("Falha ao consultar o serviço da ANA.")
        messagebox.showerror("Erro na consulta",
            "Não foi possível acessar ou interpretar a resposta do serviço da ANA.\n\n"
            f"Detalhes: {error}\n\nConfira a internet e tente novamente. O serviço legado pode ter sido alterado.")

    def export_csv(self):
        if not self.records:
            return
        path = filedialog.asksaveasfilename(
            title="Salvar dados em CSV", defaultextension=".csv",
            filetypes=[("Arquivo CSV", "*.csv")], initialfile="dados_pluviometricos.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=list(self.records[0].keys()), delimiter=";")
                writer.writeheader()
                writer.writerows(self.records)
            messagebox.showinfo("Exportação concluída", f"Arquivo salvo com sucesso:\n{path}")
        except OSError as exc:
            messagebox.showerror("Erro ao salvar", str(exc))

if __name__ == "__main__":
    App().mainloop()
