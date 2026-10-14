import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

API_URL = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos"

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

