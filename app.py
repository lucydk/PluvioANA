import csv
import io
import os
from datetime import datetime
from flask import Flask, render_template, request, make_response

from consulta_pluviometrica import fetch_data, value_of

app = Flask(__name__)


def format_records(rows, requested_station):
    records = []

    for row in rows:
        station = value_of(row, "codestacao") or requested_station
        date_time = value_of(row, "datahora")
        rain = value_of(
            row, "chuva", "precipitacao", "precipitação",
            "precipitacaomm", "chuva_mm", "valorchuva"
        )

        if not date_time and not rain:
            continue

        date_part, time_part = date_time, ""

        for fmt in (
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(date_time, fmt)
                date_part = parsed.strftime("%d/%m/%Y")
                time_part = parsed.strftime("%H:%M:%S")
                break
            except ValueError:
                continue

        records.append({
            "Código da estação": station,
            "Data": date_part,
            "Hora": time_part,
            "Precipitação (mm)": rain or "não informado",
        })

    return records


@app.route("/", methods=["GET", "POST"])
def index():
    records = []
    error = None
    station = ""
    start = ""
    end = ""

    if request.method == "POST":
        station = request.form.get("station", "").strip()
        start = request.form.get("start", "").strip()
        end = request.form.get("end", "").strip()

        try:
            if not station.isdigit():
                raise ValueError("Informe o código numérico da estação.")

            start_dt = datetime.strptime(start, "%Y-%m-%d")
            end_dt = datetime.strptime(end, "%Y-%m-%d")

            if start_dt > end_dt:
                raise ValueError(
                    "A data inicial deve ser anterior ou igual à data final."
                )

            rows = fetch_data(
                station,
                start_dt.strftime("%d/%m/%Y"),
                end_dt.strftime("%d/%m/%Y"),
            )
            records = format_records(rows, station)

            if not records:
                error = "Nenhum registro de precipitação reconhecível foi retornado."

        except ValueError as exc:
            error = str(exc)
        except Exception:
            app.logger.exception("Erro durante a consulta à ANA")
            error = (
                "Não foi possível consultar o serviço da ANA. "
                "Verifique a conexão e tente novamente."
            )

    return render_template(
        "index.html",
        records=records,
        error=error,
        station=station,
        start=start,
        end=end,
    )


@app.post("/exportar")
def export_csv():
    station = request.form.get("station", "").strip()
    start = request.form.get("start", "").strip()
    end = request.form.get("end", "").strip()

    try:
        if not station.isdigit():
            raise ValueError("Código de estação inválido.")

        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")

        if start_dt > end_dt:
            raise ValueError("O período informado é inválido.")

        rows = fetch_data(
            station,
            start_dt.strftime("%d/%m/%Y"),
            end_dt.strftime("%d/%m/%Y"),
        )
        records = format_records(rows, station)

        if not records:
            return "Não existem registros para exportar.", 404

        output = io.StringIO(newline="")
        writer = csv.DictWriter(
            output,
            fieldnames=list(records[0].keys()),
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(records)

        response = make_response(
            "\ufeff" + output.getvalue()
        )
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = (
            'attachment; filename="dados_pluviometricos.csv"'
        )
        return response

    except ValueError as exc:
        return str(exc), 400
    except Exception:
        app.logger.exception("Erro durante a exportação CSV")
        return "Não foi possível consultar os dados para exportação.", 502


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )
