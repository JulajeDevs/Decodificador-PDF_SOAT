import re
import gc
import unicodedata
from io import BytesIO

import pdfplumber
import pandas as pd
import streamlit as st

# Cargar tipos de documentos

try:
    identificacion = pd.read_excel("Tipo_Documentos.xlsx")
    tipos_identificacion = identificacion["TipoDocumento"].tolist()
except FileNotFoundError:
    tipos_identificacion = ["CC", "TI", "CE", "RC", "PA", "AS", "MS", "NU"]


MESES = {
    "ENERO": "01",
    "FEBRERO": "02",
    "MARZO": "03",
    "ABRIL": "04",
    "MAYO": "05",
    "JUNIO": "06",
    "JULIO": "07",
    "AGOSTO": "08",
    "SEPTIEMBRE": "09",
    "OCTUBRE": "10",
    "NOVIEMBRE": "11",
    "DICIEMBRE": "12",
}


def convertir_fecha_texto(fecha_raw):
    fecha_texto = re.search(r"([A-Z]+)\s+(\d{1,2})\s+DE\s+(\d{4})", fecha_raw.upper())
    if fecha_texto:
        mes = MESES.get(fecha_texto.group(1), "00")
        dia = fecha_texto.group(2).zfill(2)
        año = fecha_texto.group(3)
        return f"{dia}-{mes}-{año}"
    return None


def extraer_valor_en_pesos(valor_raw):
    if not valor_raw:
        return None

    texto = str(valor_raw).replace("\xa0", " ").strip()

    for patron in (
        r"Pesos:\s*\$?\s*([\d\.,]+)",
        r"\$\s*([\d\.,]+)",
        r"([\d]{1,3}(?:\.\d{3})*(?:,\d{2})?)",
    ):
        match = re.search(patron, texto, re.IGNORECASE)
        if not match:
            continue

        valor = match.group(1).strip()
        valor_entero = valor.split(",")[0].replace(".", "").strip()

        if valor_entero.isdigit():
            return f"${int(valor_entero):,}".replace(",", ".")

    return None


# --- FUNCIONES DE EXTRACCIÓN POR ASEGURADORA ---


def Mapfre(text):
    data = {}

    names_match = re.search(
        r"ACCIDENTADO\s+([\w\sÁÉÍÓÚÑáéíóúñ]+)\s+IDENTIFICACIÓN DE ACCIDENTADO",
        text,
        re.DOTALL,
    )
    data["Nombres y Apellidos"] = (
        names_match.group(1).strip() if names_match else "No encontrado"
    )

    id_match = re.search(
        r"IDENTIFICACIÓN DE ACCIDENTADO\s*(?:C\.?C\s*)?([\d\.]+)", text
    )
    data["Identificación"] = id_match.group(1) if id_match else "No encontrado"

    data["Tipo Identificación"] = "CC"

    policy_match = re.search(
        r"p[oó]liza\s+SOAT\s+expedida\s+por\s+(?:nuestra\s+aseguradora|nuestra\s+entidad)\s+bajo\s+el\s+n[uú]mero\s+(\d+)",
        text,
        re.IGNORECASE,
    )
    data["Numero Poliza"] = policy_match.group(1) if policy_match else "No encontrado"

    total_paid_match = re.search(
        r"(?:TOTAL|VALOR|TOTAL,)\s+(?:LIQUIDADO|PAGADO|CANCELADO|RECLAMADO)[^$]*\$\s*([\d\.,]+)",
        text,
        re.IGNORECASE,
    )
    if total_paid_match:
        valor = total_paid_match.group(1).replace(".", "").replace(",", "")
        data["Valor Pagado"] = f"${int(valor):,}".replace(",", ".")
    else:
        data["Valor Pagado"] = "No encontrado"

    coverage_match = re.search(
        r"TOPE\s+DE\s+COBERTURA[^$]+\$\s*([\d\.,]+)", text, re.IGNORECASE
    )
    if coverage_match:
        cobertura = coverage_match.group(1).replace(".", "").replace(",", "")
        data["Cobertura"] = f"${int(cobertura):,}".replace(",", ".")
    else:
        data["Cobertura"] = "No encontrado"

    if data["Valor Pagado"] != "No encontrado" and data["Cobertura"] != "No encontrado":
        try:
            valor_total = int(data["Valor Pagado"].replace("$", "").replace(".", ""))
            total_cobertura = int(data["Cobertura"].replace("$", "").replace(".", ""))

            if valor_total >= total_cobertura:
                data["Estado Cobertura"] = "AGOTADO"
            else:
                data["Estado Cobertura"] = "NO AGOTADO"
        except:
            data["Estado Cobertura"] = "No encontrado"
    else:
        data["Estado Cobertura"] = "No encontrado"

    date_match = re.search(r"FECHA DEL ACCIDENTE\s+(\d{2}/\d{2}/\d{4})", text)
    data["Fecha Siniestro"] = (
        date_match.group(1).strip() if date_match else "No encontrado"
    )

    return data


def previsora(text):
    data = {}

    match_new_id = re.search(r"(AS|ERI|[A-Z]{2})\s*(\d+[A-Z]\d+|\d{8}[A-Z]{2})", text)
    if match_new_id:
        data["Tipo Identificación"] = match_new_id.group(1).strip().upper()
        data["Identificación"] = match_new_id.group(2).strip()
    else:
        match_names_old = re.search(
            r"\b("
            + "|".join(tipos_identificacion)
            + r")\s+(\d{5,15})\s+([A-Za-zÁÉÍÓÚÑáéíóúñ0-9\s]+?)\s+\d{2}-\d{2}-\d{4}",
            text,
            re.DOTALL,
        )

        if match_names_old:
            data["Nombres y Apellidos"] = match_names_old.group(3).strip()
            data["Tipo Identificación"] = match_names_old.group(1).strip().upper()
            data["Identificación"] = match_names_old.group(2).strip()
        else:
            match_ven = re.search(
                r"ACCIDENTADO.*?(MS|AS|CC|TI)\s+(VEN\d+)\s+([A-ZÁÉÍÓÚÑ\s]+?)\s+\d{2}-\d{2}-\d{4}",
                text,
                re.DOTALL,
            )
            if match_ven:
                data["Nombres y Apellidos"] = match_ven.group(3).strip()
                data["Identificación"] = match_ven.group(2).strip()

                doc_match = re.search(
                    r"\b(" + "|".join(map(re.escape, tipos_identificacion)) + r")\b",
                    match_ven.group(0),
                )
                if doc_match:
                    data["Tipo Identificación"] = doc_match.group(1).strip().upper()
                else:
                    data["Tipo Identificación"] = "No encontrado"
            else:
                tipos_regex = "|".join(map(re.escape, tipos_identificacion))
                match_split_n = re.search(
                    r"ACCIDENTADO(?:\s+VÍCTIMA\s+SINIESTRO)?\s*\n"
                    r"(?P<nombre1>[A-ZÁÉÍÓÚÑ\s]+)"
                    r"(?:\n(?P<nombre2>(?!(" + tipos_regex + r")\b)[A-ZÁÉÍÓÚÑ\s]+))?"
                    r"\n\s*(?P<tipo>(" + tipos_regex + r"))\s*(?P<num>\d{5,15})"
                    r"(?:\s*\n\s*(?P<nombre3>[A-ZÁÉÍÓÚÑ\s]+))?",
                    text,
                    re.DOTALL,
                )
                if match_split_n:
                    nombre = match_split_n.group("nombre1").strip()
                    if match_split_n.group("nombre2"):
                        nombre += " " + match_split_n.group("nombre2").strip()
                    if match_split_n.group("nombre3"):
                        nombre += " " + match_split_n.group("nombre3").strip()
                    data["Nombres y Apellidos"] = nombre
                    data["Tipo Identificación"] = (
                        match_split_n.group("tipo").strip().upper()
                    )
                    data["Identificación"] = match_split_n.group("num").strip()
                else:
                    data.update(
                        {
                            "Nombres y Apellidos": "No encontrado",
                            "Tipo Identificación": "No encontrado",
                            "Identificación": "No encontrado",
                        }
                    )

    match_policy = re.search(r"PÓLIZA DESDE HASTA PLACA\s*(\d{13,16})", text)

    if match_policy:
        data["Numero Poliza"] = match_policy.group(1).strip()
    else:
        data["Numero Poliza"] = "No encontrado"

    if "NO HA AGOTADO" in text:
        data["Estado Cobertura"] = "NO HA AGOTADO"
    elif "HA AGOTADO" in text:
        data["Estado Cobertura"] = "HA AGOTADO"
    else:
        data["Estado Cobertura"] = "No encontrado"

    date_match = re.search(r"(\d{2}-\d{2}-\d{4})(?:\s*\$|$)", text, re.MULTILINE)
    if date_match:
        data["Fecha Siniestro"] = date_match.group(1).replace("-", "/")
    else:
        data["Fecha Siniestro"] = "No encontrado"

    valor_pagado_match = re.search(
        r"VALOR\s+PAGADO.*?[A-Z]{2}\s+\d+.*?\d{2}-\d{2}-\d{4}\s+\$\s*([\d\.,]+)",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if valor_pagado_match:
        valor = valor_pagado_match.group(1).replace(".", "").replace(",", "").strip()
        data["Valor Pagado"] = f"${int(valor):,}".replace(",", ".")
    else:
        valor_simple = re.search(r"\$\s*([\d\.]+)\s*$", text, re.MULTILINE)
        if valor_simple:
            valor = valor_simple.group(1).replace(".", "").strip()
            data["Valor Pagado"] = f"${int(valor):,}".replace(",", ".")
        else:
            data["Valor Pagado"] = "No encontrado"

    cobertura_match = re.search(
        r"COBERTURA.*?\$\s*([\d\.,]+)", text, re.IGNORECASE | re.DOTALL
    )
    if cobertura_match:
        cobertura = cobertura_match.group(1).replace(".", "").replace(",", "").strip()
        data["Cobertura"] = f"${int(cobertura):,}".replace(",", ".")
    else:
        data["Cobertura"] = "No encontrado"

    return data


def sura(text):
    data = {}

    tipos_id = "|".join(map(re.escape, tipos_identificacion))
    match_names = re.compile(
        rf"(?:Identificación\s+accidentado\s+.*?)?({tipos_id})\s+(\d+)\s+([^\d]+?)\s*\d{{2}}-\d{{2}}-\d{{4}}",
        re.DOTALL | re.IGNORECASE,
    )

    match_names = match_names.search(text)
    if match_names:
        data["Nombres y Apellidos"] = match_names.group(3).strip()
        data["Tipo Identificación"] = match_names.group(1).strip().upper()
        data["Identificación"] = match_names.group(2).strip()
    else:
        data["Nombres y Apellidos"] = "No encontrado"
        data["Tipo Identificación"] = "No encontrado"
        data["Identificación"] = "No encontrado"

    policy_match = re.search(
        r"Póliza\s+número\s+(?:Desde\s+Hasta\s+Placa\s+vehículo\s+)?(\d{8})",
        text,
        re.IGNORECASE,
    )
    data["Numero Poliza"] = (
        policy_match.group(1).strip() if policy_match else "No encontrado"
    )

    total_line_match = re.search(
        r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s+UVT\s+(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s+(\d{1,3}(?:\.\d{3})*(?:,\d+)?)",
        text,
    )
    if total_line_match:
        cobertura_raw = total_line_match.group(2).replace(".", "").replace(",", "")
        valor_pagado_raw = total_line_match.group(3).replace(".", "").replace(",", "")

        data["Cobertura"] = f"${int(cobertura_raw):,}".replace(",", ".")
        data["Valor Pagado"] = f"${int(valor_pagado_raw):,}".replace(",", ".")
    else:
        data["Cobertura"] = "No encontrado"
        data["Valor Pagado"] = "No encontrado"

    status_match = re.search(
        r"Estado\s*\n?\s*(AGOTADO|NO\s+AGOTADO)", text, re.IGNORECASE
    )
    if status_match:
        estado = status_match.group(1).strip().upper()
        data["Estado Cobertura"] = estado.replace("  ", " ")
    else:
        if "AGOTADO" in text and "NO" not in text.split("AGOTADO")[0][-20:]:
            data["Estado Cobertura"] = "AGOTADO"
        else:
            data["Estado Cobertura"] = "NO AGOTADO"

    date_match = re.search(
        r"Identificación\s+accidentado\s+Nombre\s+accidentado\s+Fecha\s+accidente\s+[A-Z]{2}\s+\d+\s+[A-ZÁÉÍÓÚÑ\s]+\s+(\d{2}-\d{2}-\d{4})",
        text,
        re.IGNORECASE,
    )

    if not date_match:
        date_match = re.search(
            r"[A-Z]{2}\s+\d+\s+[A-ZÁÉÍÓÚÑ\s]+\s+(\d{2}-\d{2}-\d{4})", text
        )

    if not date_match:
        date_match = re.search(
            r"Fecha\s+accidente\s+(\d{2}[-/]\d{2}[-/]\d{4})", text, re.IGNORECASE
        )

    if date_match:
        fecha = date_match.group(1).strip()
        fecha_normalizada = fecha.replace("-", "/")
        data["Fecha Siniestro"] = fecha_normalizada
    else:
        data["Fecha Siniestro"] = "No encontrado"

    return data


def hdi(text):
    data = {}

    match_names = re.search(
        r"Nombre de la víctima:\s*([A-ZÁÉÍÓÚÑ ]+)", text, re.IGNORECASE
    )
    data["Nombres y Apellidos"] = (
        match_names.group(1).strip() if match_names else "No encontrado"
    )

    match_id = re.search(r"Número Id víctima:\s*(\d+)", text, re.IGNORECASE)
    data["Identificación"] = (
        match_id.group(1).replace(".", "").strip() if match_id else "No encontrado"
    )

    data["Tipo Identificación"] = "CC"

    policy_match = re.search(r"Póliza:\s*(\d+)", text, re.IGNORECASE)
    data["Numero Poliza"] = policy_match.group(1) if policy_match else "No encontrado"

    date_match = re.search(
        r"(?i)Fecha\s*(?:de\s*)?accidente\s*:?\s*(\d{2}[-/]\d{2}[-/]\d{4})", text
    )
    if date_match:
        fecha = date_match.group(1).replace("-", "/")
        data["Fecha Siniestro"] = fecha
    else:
        data["Fecha Siniestro"] = "No encontrado"

    total_paid_match = re.search(
        r"(?:Valor\s*total\s*pagado\s*:|TOTAL PAGADO AMPARO)\s*\$\s*([\d.,]+)",
        text,
        re.IGNORECASE,
    )
    if total_paid_match:
        valor_raw = total_paid_match.group(1).strip()
        valor_num = int(valor_raw.replace(".", "").replace(",", ""))
        data["Valor Pagado"] = f"${valor_num:,}".replace(",", ".")
    else:
        data["Valor Pagado"] = "No encontrado"

    coverage_match = re.search(
        r"Valor\s*total\s*de\s*UVT:\s*[\d.,]+\s*Valor\s*total\s*pagado:\s*\$\s*([\d.,]+)",
        text,
        re.IGNORECASE,
    )
    if coverage_match:
        cobertura_raw = coverage_match.group(1).strip()
        cobertura_num = int(cobertura_raw.replace(".", "").replace(",", ""))
        data["Cobertura"] = f"${cobertura_num:,}".replace(",", ".")
    else:
        data["Cobertura"] = "No encontrado"

    if data["Valor Pagado"] != "No encontrado" and data["Cobertura"] != "No encontrado":
        try:
            valor_pagado_num = int(
                data["Valor Pagado"].replace("$", "").replace(".", "")
            )
            cobertura_num = int(data["Cobertura"].replace("$", "").replace(".", ""))

            if valor_pagado_num >= cobertura_num:
                data["Estado Cobertura"] = "AGOTADO"
            else:
                data["Estado Cobertura"] = "NO AGOTADO"
        except:
            data["Estado Cobertura"] = "No encontrado"
    else:
        data["Estado Cobertura"] = "No encontrado"

    return data


def indemnizaciones(text):
    data = {}

    name_match = re.search(
        r"(?:La señora|El señor)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]+),\s*identificad[ao] con",
        text,
        re.IGNORECASE,
    )
    data["Nombres y Apellidos"] = (
        name_match.group(1).strip() if name_match else "No encontrado"
    )

    id_match = re.search(
        r"Cédula de\s+Ciudadanía[\s\n]*([\d\.,]+)", text, re.IGNORECASE
    )
    data["Identificacion"] = (
        id_match.group(1).replace(".", "") if id_match else "No encontrado"
    )

    policy_match = re.search(r"POLIZA SOAT No\.\s*(\d+)", text, re.IGNORECASE)
    data["Numero Poliza"] = policy_match.group(1) if policy_match else "No encontrado"

    no_present_match = re.search(
        r"NO HA PRESENTADO PAGOS POR CONCEPTOS DE GASTOS MEDICOS", text, re.IGNORECASE
    )
    data["Concepto Gastos"] = (
        "NO HA PRESENTADO GASTOS MÉDICOS" if no_present_match else "No encontrado"
    )

    return data


def bolivar(text):
    data = {}

    name_match = re.search(
        r"([A-Z]{2,})\s+(\d+)\s+([A-ZÁÉÍÓÚÑ\s]+?)\s+\d{2}-\d{2}-\d{4}",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if name_match:
        data["Nombres y Apellidos"] = name_match.group(3).strip()
        data["Identificación"] = name_match.group(2).strip()
        data["Tipo Identificación"] = name_match.group(1).strip()
    else:
        data.update(
            {
                "Nombres y Apellidos": "No Encontrado",
                "Identificación": "No Encontrado",
                "Tipo Identificación": "No Encontrado",
            }
        )

    policy_match = re.search(
        r"(?:Póliza\s+Número.*?(\d{13,})|(?:No\.|numero)\s*(\d+))",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    data["Numero Poliza"] = policy_match.group(1) if policy_match else "No encontrado"

    total_line_match = re.search(r"(\d+\.\d+)\s+\$\s+([\d.]+)\s+\$\s+([\d.]+)", text)
    if total_line_match:
        data["Cobertura"] = total_line_match.group(2)
        data["Valor Pagado"] = total_line_match.group(3)
    else:
        data["Cobertura"] = "No encontrado"
        data["Valor Pagado"] = "No encontrado"

    try:
        valor_pagado = int(data["Valor Pagado"].replace(".", ""))
        cobertura = int(data["Cobertura"].replace(".", ""))
        if valor_pagado >= cobertura:
            data["Estado Cobertura"] = "AGOTADO"
        else:
            data["Estado Cobertura"] = "NO AGOTADO"
    except:
        data["Estado Cobertura"] = "No encontrado"

    match_date = re.search(r"Fecha Accidente.*?(\d{2}-\d{2}-\d{4})", text, re.DOTALL)
    data["Fecha Siniestro"] = match_date.group(1) if match_date else "No encontrado"

    return data


def seg_mundial(text, pdf=None):
    # Inicializar diccionario con formato estandarizado
    data = {
        "Nombres y Apellidos": "No encontrado",
        "Numero Poliza": "No encontrado",
        "Fecha Siniestro": "No encontrado",
        "Estado Cobertura": "No encontrado",
        "Cobertura": "No encontrado",
        "Valor Pagado": "No encontrado",
        "Identificación": "No encontrado",  # <-- Estandarizado
        "Tipo Identificación": "No encontrado",  # <-- Estandarizado
    }

    found_in_table = False

    # --- ESTRATEGIA 1: EXTRACCIÓN POR TABLAS (MEJORA) ---
    if pdf:
        try:
            for page in pdf.pages:
                tables = page.extract_tables()

                for table in tables:
                    header_idx = -1
                    col_indices = {}

                    for i, row in enumerate(table):
                        # Limpieza básica de la fila para buscar cabeceras
                        row_clean = [
                            str(c).upper().replace("\n", " ") if c else "" for c in row
                        ]

                        if "AFECTADO" in row_clean and "AMPARO" in row_clean:
                            header_idx = i
                            # Mapear columnas dinámicamente
                            try:
                                col_indices["AFECTADO"] = row_clean.index("AFECTADO")
                                col_indices["AMPARO"] = row_clean.index("AMPARO")
                                # Buscar otras columnas aproximadas
                                for idx, col_name in enumerate(row_clean):
                                    if "FECHA" in col_name and "ACCIDENTE" in col_name:
                                        col_indices["FECHA"] = idx
                                    if "POLIZA" in col_name:
                                        col_indices["POLIZA"] = idx
                                    if "ESTADO" in col_name:
                                        col_indices["ESTADO"] = idx
                                    if "TOPE" in col_name:
                                        col_indices["TOPE"] = idx
                                    if "PAGADO" in col_name:
                                        col_indices["PAGADO"] = idx
                                    if "SALDO" in col_name:
                                        col_indices["SALDO"] = idx
                            except:
                                pass
                            break

                    if header_idx != -1:
                        for row in table[header_idx + 1 :]:
                            idx_afectado = col_indices.get("AFECTADO", 0)
                            idx_amparo = col_indices.get("AMPARO", 1)

                            if len(row) > idx_amparo:
                                amparo_val = (
                                    str(row[idx_amparo]).upper()
                                    if row[idx_amparo]
                                    else ""
                                )
                                if "GASTOS MEDICOS" in amparo_val:
                                    # --- EXTRACCIÓN DEL NOMBRE ---
                                    raw_name = row[idx_afectado]
                                    if raw_name:
                                        full_name = raw_name.replace("\n", " ").strip()
                                        full_name = re.sub(
                                            r"^SEGUROS\s+MUNDIAL\s*",
                                            "",
                                            full_name,
                                            flags=re.IGNORECASE,
                                        ).strip()
                                        data["Nombres y Apellidos"] = full_name
                                        found_in_table = True

                                    # --- EXTRACCIÓN DEL RESTO DE DATOS (MISMA FILA) ---
                                    # Fecha
                                    if (
                                        "FECHA" in col_indices
                                        and len(row) > col_indices["FECHA"]
                                    ):
                                        val = row[col_indices["FECHA"]]
                                        if val:
                                            data["Fecha Siniestro"] = val.replace(
                                                "\n", " "
                                            ).strip()

                                    # Póliza
                                    if (
                                        "POLIZA" in col_indices
                                        and len(row) > col_indices["POLIZA"]
                                    ):
                                        val = row[col_indices["POLIZA"]]
                                        if val:
                                            data["Numero Poliza"] = val.replace(
                                                "\n", " "
                                            ).strip()

                                    # Cobertura (Tope)
                                    if (
                                        "TOPE" in col_indices
                                        and len(row) > col_indices["TOPE"]
                                    ):
                                        val = row[col_indices["TOPE"]]
                                        if val:
                                            data["Cobertura"] = (
                                                extraer_valor_en_pesos(val)
                                                or val.replace("\n", " ").strip()
                                            )

                                    # Valor pagado
                                    if (
                                        "PAGADO" in col_indices
                                        and len(row) > col_indices["PAGADO"]
                                    ):
                                        val = row[col_indices["PAGADO"]]
                                        if val:
                                            data["Valor Pagado"] = (
                                                extraer_valor_en_pesos(val)
                                                or val.replace("\n", " ").strip()
                                            )

                                    # Estado
                                    if (
                                        "ESTADO" in col_indices
                                        and len(row) > col_indices["ESTADO"]
                                    ):
                                        val = str(row[col_indices["ESTADO"]]).upper()
                                        if val:
                                            if "NO" in val and "AGOTADA" in val:
                                                data["Estado Cobertura"] = "NO AGOTADO"
                                            elif "AGOTADA" in val:
                                                data["Estado Cobertura"] = "AGOTADO"
                                            else:
                                                data["Estado Cobertura"] = val

                                    return data
        except Exception as e:
            pass

    # --- ESTRATEGIA 2: REGEX (FALLBACK SI FALLA LA TABLA) ---
    if not found_in_table:

        name_match = re.search(
            r"Afectado\s+(?:Amparo\s+)?(?:Fecha\s+Accidente\s+)?(?:Póliza\s+)?(?:Siniestro\s+)?(?:Estado\s+)?(?:Tope\s+)?(?:Saldo\s+)?((?:[A-ZÁÉÍÓÚÑ]+\s*)+)\s+(?:Gastos|Amparo)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if name_match:
            data["Nombres y Apellidos"] = re.sub(
                r"\s+", " ", name_match.group(1).strip()
            )

        policy_match = re.search(
            r"\d{2}/\d{2}/\d{4}\s+(\d{4}-\d{8}\.\d)", text, re.IGNORECASE
        )
        if policy_match:
            data["Numero Poliza"] = policy_match.group(1).strip()

        estado_match = re.search(
            r"(?:Estado\s+)?(?:Cobertura\s+)?(Agotada|NO\s+Agotada|No\s+Agotada)",
            text,
            re.IGNORECASE,
        )
        if estado_match:
            estado = estado_match.group(1).strip().upper()
            if "AGOTADA" in estado and "NO" not in estado:
                data["Estado Cobertura"] = "AGOTADO"
            else:
                data["Estado Cobertura"] = "NO AGOTADO"

        if re.search(r"no\s+se\s+identifican\s+reclamaciones", text, re.IGNORECASE):
            data["Estado Cobertura"] = "SIN RECLAMACIONES"

        date_match = re.search(
            r"Fecha\s+Accidente.*?(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE | re.DOTALL
        )
        if date_match:
            fecha = date_match.group(1).strip().replace("/", "-")
            data["Fecha Siniestro"] = fecha

    return data


def colpatria_axa(text):
    data = {}

    name_match = re.search(
        r"(?:Lesionado\s*\(a\)\s*:|AFECTADO\s*/\s*LESIONADO)\s+(.*)",
        text,
        re.IGNORECASE,
    )
    data["Nombres y Apellidos"] = name_match.group(1).strip() if name_match else None

    type_id = re.search(r"Tipo\s+ID\s+Lesionado\s*:\s*(.*)", text, re.IGNORECASE)
    tipo_identificacion_raw = type_id.group(1).strip() if type_id else "No encontrado"

    if tipo_identificacion_raw and tipo_identificacion_raw != "No encontrado":
        tipo_identificacion_raw = tipo_identificacion_raw.upper()

        if (
            "CEDULA DE CIUDADANIA" in tipo_identificacion_raw
            or "CÉDULA DE CIUDADANÍA" in tipo_identificacion_raw
        ):
            data["Tipo Identificación"] = "CC"
        elif (
            "CEDULA DE EXTRANJERIA" in tipo_identificacion_raw
            or "CÉDULA DE EXTRANJERÍA" in tipo_identificacion_raw
        ):
            data["Tipo Identificación"] = "CE"
        elif "TARJETA DE IDENTIDAD" in tipo_identificacion_raw:
            data["Tipo Identificación"] = "TI"
        else:
            for tipo in tipos_identificacion:
                if (
                    tipo.upper() in tipo_identificacion_raw
                    or tipo_identificacion_raw in tipo.upper()
                ):
                    data["Tipo Identificación"] = tipo.upper()
                    break
            else:
                data["Tipo Identificación"] = tipo_identificacion_raw[:3]
    else:
        data["Tipo Identificación"] = "No encontrado"

    number_id = re.search(
        r"Numero\s+de\s+ID\s+Lesionado\s*:\s*(\d+)", text, re.IGNORECASE
    )
    data["Identificación"] = (
        number_id.group(1).strip() if number_id else "No encontrado"
    )

    accident_date = re.search(
        r"(?:Fecha\s+Ocurrencia\s*:|FECHA\s+OCURRENCIA\s+SINIESTRO)\s+(.*)",
        text,
        re.IGNORECASE,
    )
    if accident_date:
        fecha_raw = accident_date.group(1).strip()
        fecha_convertida = convertir_fecha_texto(fecha_raw)
        if fecha_convertida:
            data["Fecha Siniestro"] = fecha_convertida
        else:
            fecha_normalizada = fecha_raw.replace("/", "-")
            data["Fecha Siniestro"] = fecha_normalizada
    else:
        data["Fecha Siniestro"] = None

    policy_number = "No encontrado"

    policy_match_new = re.search(
        r"número\s+AT\s+\d+\s*-\s*(\d+)(?=\s+placa)",
        text,
        re.IGNORECASE,
    )
    if policy_match_new:
        policy_number = policy_match_new.group(1).strip()
    else:
        policy_match = re.search(
            r"(?:No\.\s*Póliza\s*:\s*([\d\-]+)|número\s+([\d\-]+)(?=\s+placa))",
            text,
            re.IGNORECASE,
        )
        if policy_match:
            if policy_match.group(1):
                policy_number = policy_match.group(1).strip()
            elif policy_match.group(2):
                policy_number = policy_match.group(2).strip()

    data["Numero Poliza"] = policy_number

    status_match_new = re.search(
        r"COBERTURA\s+AGOTADA\s*(?:[:\-]?\s*)?(SI|NO)\b", text, re.IGNORECASE
    )
    if status_match_new:
        estado_si_no = status_match_new.group(1).strip().upper()
        data["Estado Cobertura"] = "AGOTADO" if estado_si_no == "SI" else "NO AGOTADO"
    else:
        status_match = re.search(r"Estado\s+AGOTADO", text, re.IGNORECASE)
        if status_match:
            data["Estado Cobertura"] = "AGOTADO"
        else:
            status_match_old = re.search(r"(NO\s+AGOTADO|AGOTADO)", text, re.IGNORECASE)
            if status_match_old:
                estado = status_match_old.group(1).strip().upper()
                data["Estado Cobertura"] = estado.replace("  ", " ")
            else:
                data["Estado Cobertura"] = "No encontrado"

    table_match = re.search(
        r"(\d+\.?\d*)\s+UVT\s+\$\s*([\d.,]+)\s+\$\s*([\d.,]+)", text, re.IGNORECASE
    )

    if table_match:
        cobertura_raw = table_match.group(2).strip()
        cobertura_num = int(cobertura_raw.replace(".", "").replace(",", ""))
        data["Cobertura"] = f"{cobertura_num:,}".replace(",", ".")

        valor_pagado_raw = table_match.group(3).strip()
        valor_pagado_num = int(valor_pagado_raw.replace(".", "").replace(",", ""))
        data["Valor Pagado"] = f"{valor_pagado_num:,}".replace(",", ".")
    else:
        coverage_new_match = re.search(
            r"TOPE\s+M\S*XIMO\s+DE\s+COBERTURA(?:\s+GASTO\s+MEDICO)?(?:\s+\S+\s+\d{4})?\s*\$?\s*([\d.,]+)",
            text,
            re.IGNORECASE,
        )
        if coverage_new_match:
            cobertura_raw = coverage_new_match.group(1).strip()
            cobertura_num = int(cobertura_raw.replace(".", "").replace(",", ""))
            data["Cobertura"] = f"{cobertura_num:,}".replace(",", ".")
        else:
            data["Cobertura"] = None
        data["Valor Pagado"] = None

    return data


def solidaria(text, pdf=None):
    data = {
        "Nombres y Apellidos": "No encontrado",
        "Identificación": "No encontrado",
        "Tipo Identificación": "No encontrado",
        "Numero Poliza": "No encontrado",
        "Fecha Siniestro": "No encontrado",
        "Estado Cobertura": "No encontrado",
        "Cobertura": "No encontrado",
        "Valor Pagado": "No encontrado",
    }

    def _clean_cell(value):
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    def _normalize_header(value):
        cleaned = _clean_cell(value).upper()
        normalized = unicodedata.normalize("NFD", cleaned)
        return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")

    def _get_by_index(row, idx):
        if idx is None or idx < 0 or idx >= len(row):
            return ""
        return _clean_cell(row[idx])

    def _find_idx(headers, condition):
        for idx, header in enumerate(headers):
            if condition(header):
                return idx
        return None

    def _format_money(value):
        money_text = _clean_cell(value)
        if not money_text:
            return "No encontrado"
        number_match = re.search(r"[\d][\d\.,]*", money_text)
        if not number_match:
            return "No encontrado"
        digits = re.sub(r"[^\d]", "", number_match.group(0))
        if not digits:
            return "No encontrado"
        return f"${int(digits):,}".replace(",", ".")

    def _normalize_estado(value):
        estado = _normalize_header(value)
        if not estado:
            return "No encontrado"
        has_agotado = "AGOTADO" in estado or "AGOTADA" in estado
        has_no = (
            "NO AGOTADO" in estado or "NO AGOTADA" in estado or " NO " in f" {estado} "
        )
        if has_agotado and not has_no:
            return "AGOTADO"
        if has_agotado and has_no:
            return "NO AGOTADO"
        return estado

    def _is_victim_header(header):
        return "VICTIMA" in header or ("CTIMA" in header and header.startswith("V"))

    policy_pair_match = re.search(
        r"SOAT\s+(\d+)\s*-\s*(\d+)", text, re.IGNORECASE | re.DOTALL
    )
    if policy_pair_match:
        data["Numero Poliza"] = policy_pair_match.group(2).strip()
    else:
        policy_single_match = re.search(
            r"SOAT(?:\s+No\.?)?\s*-\s*(\d+)", text, re.IGNORECASE | re.DOTALL
        )
        if policy_single_match:
            data["Numero Poliza"] = policy_single_match.group(1).strip()
        else:
            policy_no_match = re.search(
                r"SOAT\s+No\.?\s*(\d+)", text, re.IGNORECASE | re.DOTALL
            )
            if policy_no_match:
                data["Numero Poliza"] = policy_no_match.group(1).strip()

    if pdf:
        try:
            victim_table_found = False
            coverage_table_found = False

            for page in pdf.pages:
                tables = page.extract_tables() or []

                for table in tables:
                    if not table:
                        continue

                    for row_idx, row in enumerate(table):
                        if not row:
                            continue

                        headers = [_normalize_header(cell) for cell in row]

                        idx_name = _find_idx(headers, _is_victim_header)
                        idx_doc = _find_idx(headers, lambda h: "DOCUMENTO" in h)
                        idx_ident = _find_idx(headers, lambda h: "IDENTIFICACION" in h)
                        idx_siniestro = _find_idx(headers, lambda h: "SINIESTRO" in h)
                        idx_date = _find_idx(
                            headers, lambda h: "FECHA" in h and "ACCIDENTE" in h
                        )

                        has_victim_headers = (
                            idx_name is not None
                            and idx_date is not None
                            and (
                                idx_doc is not None
                                or idx_ident is not None
                                or idx_siniestro is not None
                            )
                        )
                        if has_victim_headers and not victim_table_found:
                            for candidate_row in table[row_idx + 1 :]:
                                if not candidate_row:
                                    continue
                                name_value = _get_by_index(candidate_row, idx_name)
                                doc_value = _get_by_index(
                                    candidate_row,
                                    idx_doc if idx_doc is not None else idx_ident,
                                )
                                siniestro_value = _get_by_index(
                                    candidate_row, idx_siniestro
                                )
                                date_value = _get_by_index(candidate_row, idx_date)
                                if not (
                                    name_value
                                    or doc_value
                                    or siniestro_value
                                    or date_value
                                ):
                                    continue

                                if name_value:
                                    data["Nombres y Apellidos"] = re.sub(
                                        r"\s+", " ", name_value
                                    ).strip()
                                if doc_value:
                                    data["Identificación"] = re.sub(
                                        r"\s+", "", doc_value
                                    ).replace(".", "")
                                elif siniestro_value:
                                    siniestro_digits = re.sub(
                                        r"[^\d]", "", siniestro_value
                                    )
                                    if len(siniestro_digits) >= 7:
                                        data["Identificación"] = siniestro_digits
                                if date_value:
                                    date_match = re.search(
                                        r"\d{2}[/-]\d{2}[/-]\d{4}", date_value
                                    )
                                    data["Fecha Siniestro"] = (
                                        date_match.group(0).replace("-", "/")
                                        if date_match
                                        else date_value
                                    )
                                victim_table_found = True
                                break

                        has_coverage_headers = (
                            any("VALOR COBERTURA" in h for h in headers)
                            and any("VALOR CANCELADO" in h for h in headers)
                            and any("ESTADO" in h for h in headers)
                        )
                        if has_coverage_headers and not coverage_table_found:
                            idx_cov = _find_idx(
                                headers, lambda h: "VALOR COBERTURA" in h
                            )
                            idx_paid = _find_idx(
                                headers, lambda h: "VALOR CANCELADO" in h
                            )
                            idx_status = _find_idx(headers, lambda h: "ESTADO" in h)

                            for candidate_row in table[row_idx + 1 :]:
                                if not candidate_row:
                                    continue
                                cov_value = _get_by_index(candidate_row, idx_cov)
                                paid_value = _get_by_index(candidate_row, idx_paid)
                                status_value = _get_by_index(candidate_row, idx_status)
                                if not (cov_value or paid_value or status_value):
                                    continue

                                data["Cobertura"] = _format_money(cov_value)
                                data["Valor Pagado"] = _format_money(paid_value)
                                data["Estado Cobertura"] = _normalize_estado(
                                    status_value
                                )
                                coverage_table_found = True
                                break

                    if victim_table_found and coverage_table_found:
                        break

                if victim_table_found and coverage_table_found:
                    break
        except Exception:
            pass

    if data["Nombres y Apellidos"] == "No encontrado":
        victim_match = re.search(
            r"V\S*CTIMA\s+(?:DOCUMENTO|IDENTIFICACI[ÓO]N|SINIESTRO)\s+FECHA\s+ACCIDENTE\s+(.+?)\s+(\d{5,15})\s+(\d{2}/\d{2}/\d{4})",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if victim_match:
            data["Nombres y Apellidos"] = re.sub(
                r"\s+", " ", victim_match.group(1).strip()
            )
            data["Identificación"] = victim_match.group(2).strip()
            data["Fecha Siniestro"] = victim_match.group(3).strip()

    if data["Cobertura"] == "No encontrado":
        coverage_match = re.search(
            r"VALOR\s+COBERTURA\s+PESOS.*?\$\s*([\d\.,]+)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if coverage_match:
            data["Cobertura"] = _format_money(coverage_match.group(1))

    if data["Valor Pagado"] == "No encontrado":
        paid_match = re.search(
            r"VALOR\s+CANCELADO.*?\$\s*([\d\.,]+)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if paid_match:
            data["Valor Pagado"] = _format_money(paid_match.group(1))

    if data["Estado Cobertura"] == "No encontrado":
        status_match = re.search(
            r"ESTADO\s+(AGOTADO|NO\s+AGOTADO|NO\s+AGOTADA|AGOTADA)",
            text,
            re.IGNORECASE,
        )
        if status_match:
            data["Estado Cobertura"] = _normalize_estado(status_match.group(1))
        else:
            generic_status = re.search(
                r"\b(NO\s+AGOTAD[AO]|AGOTAD[AO])\b",
                text,
                re.IGNORECASE,
            )
            if generic_status:
                data["Estado Cobertura"] = _normalize_estado(generic_status.group(1))

    return data


def seg_estados(text):
    data = {}

    afectado_match = re.search(r"AFECTADO\s+(\d+)-([^\n]+)", text, re.IGNORECASE)
    if afectado_match:
        data["Identificación"] = afectado_match.group(1).strip()
        data["Nombres y Apellidos"] = afectado_match.group(2).strip()
    else:
        data["Nombres y Apellidos"] = "No encontrado"
        data["Identificación"] = "No encontrado"

    data["Tipo Identificación"] = "CC"

    number_policy = re.search(
        r"(?:póliza.*?)?No\.\s*(\d+)", text, re.IGNORECASE | re.DOTALL
    )
    data["Numero Poliza"] = (
        number_policy.group(1).strip() if number_policy else "No encontrado"
    )

    date = re.search(
        r"FECHA\s+DE\s+SINIESTRO\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE
    )
    if date:
        fecha_raw = date.group(1).strip()
        data["Fecha Siniestro"] = fecha_raw.replace("/", "-")
    else:
        data["Fecha Siniestro"] = "No encontrado"

    coverage_status = re.search(
        r"ESTADO\s+([A-Za-zÁÉÍÓÚÑáéíóúñ\s]+?)(?=\n|$)", text, re.IGNORECASE
    )
    if not coverage_status:
        coverage_status = re.search(
            r"(Cobertura\s+Agotada|Cobertura\s+No\s+Agotada)", text, re.IGNORECASE
        )

    if coverage_status:
        estado = coverage_status.group(1).strip().upper()
        if "AGOTADA" in estado or "AGOTADO" in estado:
            if "NO" not in estado:
                data["Estado Cobertura"] = "AGOTADO"
            else:
                data["Estado Cobertura"] = "NO AGOTADO"
        else:
            data["Estado Cobertura"] = estado
    else:
        data["Estado Cobertura"] = "No encontrado"

    cobertura_match = re.search(
        r"Cobertura.*?es\s+de\s+\$\s*([\d\.,]+)", text, re.IGNORECASE | re.DOTALL
    )

    if not cobertura_match:
        cobertura_match = re.search(
            r"(?:la\s+)?Cobertura.*?\$\s*([\d\.,]+)\s+\$\s*[\d\.,]+\s+\$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    if cobertura_match:
        cobertura_raw = cobertura_match.group(1).strip()
        cobertura_num = int(cobertura_raw.replace(".", "").replace(",", ""))
        data["Cobertura"] = f"${cobertura_num:,}".replace(",", ".")
    else:
        data["Cobertura"] = "No encontrado"

    data["Valor Pagado"] = "No encontrado"

    return data


def equidad(text):
    data = {}

    name_match = re.search(
        r"Nombre\s+completo\s*:\s*([A-ZÁÉÍÓÚÑ\s]+?)(?:\s*\n|\s*Fecha)",
        text,
        re.IGNORECASE,
    )

    if name_match:
        nombre_limpio = name_match.group(1).strip()
        nombre_limpio = re.sub(r"\s+", " ", nombre_limpio)
        data["Nombres y Apellidos"] = nombre_limpio
    else:
        data["Nombres y Apellidos"] = "No encontrado"

    id_match = re.search(
        r"(CÉDULA\s+DE\s+CIUDADANÍA|CEDULA\s+DE\s+CIUDADANIA)\s+No\.\s*(\d+)",
        text,
        re.IGNORECASE,
    )

    if id_match:
        data["Tipo Identificación"] = "CC"
        data["Identificación"] = id_match.group(2).strip()
    else:
        tipo_doc_match = re.search(
            r"Tipo\s+documento\s+victima\s*:\s*([A-ZÁÉÍÓÚÑ\s]+?)(?:\s*\n)",
            text,
            re.IGNORECASE,
        )
        num_doc_match = re.search(
            r"Numero\s+documento\s+victima\s*:\s*(\d+)", text, re.IGNORECASE
        )

        if tipo_doc_match:
            tipo_raw = tipo_doc_match.group(1).strip().upper()
            if "CEDULA" in tipo_raw or "CÉDULA" in tipo_raw:
                data["Tipo Identificación"] = "CC"
            else:
                data["Tipo Identificación"] = tipo_raw[:3]
        else:
            data["Tipo Identificación"] = "No encontrado"

        if num_doc_match:
            data["Identificación"] = num_doc_match.group(1).strip()
        else:
            data["Identificación"] = "No encontrado"

    policy_match = re.search(r"Póliza\s+SOAT\s+número\s+([\d\-]+)", text, re.IGNORECASE)
    if not policy_match:
        policy_match = re.search(
            r"Numero\s+de\s+poliza\s*:\s*([\d\-]+)", text, re.IGNORECASE
        )

    if policy_match:
        data["Numero Poliza"] = policy_match.group(1).strip()
    else:
        data["Numero Poliza"] = "No encontrado"

    date_match = re.search(
        r"accidente\s+vial\s+ocurrido\s+en\s+([A-Z]+)\s+(\d{1,2})\s+DE\s+(\d{4})",
        text,
        re.IGNORECASE,
    )

    if date_match:
        fecha_raw = date_match.group(0)
        fecha_convertida = convertir_fecha_texto(fecha_raw)
        data["Fecha Siniestro"] = (
            fecha_convertida if fecha_convertida else "No encontrado"
        )
    else:
        data["Fecha Siniestro"] = "No encontrado"

    estado_match = re.search(
        r"263\.13\s+UVT\s+\$[\d\.,]+\s+\$[\d\.,]+\s+\d+\s+(AGOTADO|NO\s+AGOTADO)",
        text,
        re.IGNORECASE,
    )

    if estado_match:
        estado = estado_match.group(1).strip().upper()
        data["Estado Cobertura"] = estado.replace("  ", " ")
    else:
        data["Estado Cobertura"] = "No encontrado"

    cobertura_match = re.search(
        r"Valor\s+de\s+cobertura\s+en\s+Pesos\s+Valor\s+Cancelado.*?\$\s*([\d\.,]+)\s+\$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not cobertura_match:
        cobertura_match = re.search(
            r"263\.13\s+UVT\s+\$\s*([\d\.,]+)\s+\$", text, re.IGNORECASE
        )

    if cobertura_match:
        cobertura_raw = cobertura_match.group(1).strip()
        cobertura_num = int(cobertura_raw.replace(".", "").replace(",", ""))
        data["Cobertura"] = f"${cobertura_num:,}".replace(",", ".")
    else:
        data["Cobertura"] = "No encontrado"

    cancelado_match = re.search(
        r"Valor\s+Cancelado\s+en\s+Pesos\s+Valor\s+Disponible.*?\$[\d\.,]+\s+\$\s*([\d\.,]+)\s+",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not cancelado_match:
        cancelado_match = re.search(
            r"263\.13\s+UVT\s+\$[\d\.,]+\s+\$\s*([\d\.,]+)\s+\d+", text, re.IGNORECASE
        )

    if cancelado_match:
        cancelado_raw = cancelado_match.group(1).strip()
        cancelado_num = int(cancelado_raw.replace(".", "").replace(",", ""))
        data["Valor Pagado"] = f"${cancelado_num:,}".replace(",", ".")
    else:
        data["Valor Pagado"] = "No encontrado"

    return data


# --- PROCESAMIENTO PRINCIPAL ---


def extract_data(text, pdf_file, pdf_obj=None):
    if re.search(r"MAPFRE SEGUROS GENERALES DE COLOMBIA", text, re.IGNORECASE):
        data = Mapfre(text)
        return {**data, "Nombre archivo": pdf_file, "Aseguradora": "MAPFRE"}
    elif re.search(r"PREVISORA S.A.", text, re.IGNORECASE):
        data = previsora(text)
        return {**data, "Nombre archivo": pdf_file, "Aseguradora": "PREVISORA S.A."}
    elif re.search(r"SURAMERICANA S.A", text, re.IGNORECASE):
        data = sura(text)
        return {**data, "Nombre archivo": pdf_file, "Aseguradora": "SURA"}
    elif re.search(
        r"HDI SEGUROS COLOMBIA|CERTIFICADO DE AGOTAMIENTO DE COBERTURA",
        text,
        re.IGNORECASE,
    ):
        data = hdi(text)
        return {**data, "Nombre archivo": pdf_file, "Aseguradora": "HDI SEGUROS"}
    elif re.search(r"LLAC", text, re.IGNORECASE):
        data = indemnizaciones(text)
        return {**data, "Nombre archivo": pdf_file, "Aseguradora": "LLAC"}
    elif re.search(r"SEGUROS\s+BOLIVAR\b.*?S\.A\.", text, re.IGNORECASE | re.DOTALL):
        data = bolivar(text)
        return {**data, "Nombre archivo": pdf_file, "Aseguradora": "SEGUROS BOLIVAR"}
    elif re.search(r"SEGUROS MUNDIAL", text, re.IGNORECASE):
        # Pasamos el objeto PDF a Mundial para extracción de tablas
        data = seg_mundial(text, pdf_obj)
        return {**data, "Nombre archivo": pdf_file, "Aseguradora": "SEGUROS MUNDIAL"}
    elif re.search(r"AXA COLPATRIA SEGUROS", text, re.IGNORECASE):
        data = colpatria_axa(text)
        return {**data, "Nombre archivo": pdf_file, "Aseguradora": "AXA COLPATRIA"}
    elif re.search(r"(?i)SEGUROS DEL ESTADO S\.A\.", text):
        data = seg_estados(text)
        return {**data, "Nombre archivo": pdf_file, "Aseguradora": "SEGUROS DEL ESTADO"}
    elif re.search(r"ASEGURADORA SOLIDARIA DE COLOMBIA", text):
        data = solidaria(text, pdf_obj)
        return {
            **data,
            "Nombre archivo": pdf_file,
            "Aseguradora": "ASEGURADORA SOLIDARIA",
        }
    elif re.search(r"EQUIDAD SEGUROS|LA COMPAÑÍA EQUIDAD SEGUROS", text, re.IGNORECASE):
        data = equidad(text)
        return {**data, "Nombre archivo": pdf_file, "Aseguradora": "EQUIDAD SEGUROS"}
    else:
        raise ValueError("No se pudo identificar nombre de SOAT")


def main():
    st.title("Procesador de PDFs SOAT (Completo y Optimizado)")
    st.write("Sube los archivos PDF para extraer la información")

    # Widget para subir archivos
    uploaded_files = st.file_uploader(
        "Sube tus archivos PDF", type="pdf", accept_multiple_files=True
    )

    if uploaded_files:
        results = []
        errors = []

        # Barra de progreso
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, uploaded_file in enumerate(uploaded_files):
            try:
                # Actualizar progreso
                progress = (i + 1) / len(uploaded_files)
                progress_bar.progress(progress)
                status_text.text(
                    f"Procesando archivo {i+1} de {len(uploaded_files)}: {uploaded_file.name}"
                )

                # Mover el puntero al inicio
                uploaded_file.seek(0)

                # Usar pdfplumber dentro del bucle y pasar el objeto al extractor
                text = ""
                with pdfplumber.open(uploaded_file) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"

                    if not text.strip():
                        st.warning(
                            f"El archivo {uploaded_file.name} no contiene texto extraible"
                        )
                        continue

                    # Procesar el archivo pasando texto Y el objeto pdf
                    data = extract_data(text, uploaded_file.name, pdf)
                    results.append(data)

                # Liberar memoria después de cada archivo pesado
                if i % 10 == 0:
                    gc.collect()

            except Exception as e:
                st.warning(f"Error en {uploaded_file.name}: {str(e)}")
                errors.append(uploaded_file.name)

        # Mostrar resultados
        if results:
            df = pd.DataFrame(results)

            # Normalizar formato de fechas a DD-MM-YYYY
            if "Fecha Siniestro" in df.columns:
                df["Fecha Siniestro"] = df["Fecha Siniestro"].apply(
                    lambda x: (
                        x.replace("/", "-")
                        if isinstance(x, str) and x != "No encontrado"
                        else x
                    )
                )

            # Normalizar Estado Cobertura
            if "Estado Cobertura" in df.columns:

                def normalizar_estado(estado):
                    if isinstance(estado, str) and estado != "No encontrado":
                        estado_upper = estado.upper().strip()
                        if "AGOTADO" in estado_upper:
                            if "NO" in estado_upper or "NO AGOTADO" in estado_upper:
                                return "NO AGOTADO"
                            else:
                                return "AGOTADO"
                    return estado

                df["Estado Cobertura"] = df["Estado Cobertura"].apply(normalizar_estado)

            # Mostrar vista previa
            st.subheader("Vista previa de los datos")
            st.dataframe(df)

            # Generar archivo Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Datos SOAT")

            # Botón de descarga
            st.download_button(
                label="Descargar Excel",
                data=output.getvalue(),
                file_name="resultados_soat.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            if errors:
                st.warning(f"Archivos con errores: {', '.join(errors)}")

            # Resetear progreso
            progress_bar.empty()
            status_text.text("Proceso completado exitosamente!")


if __name__ == "__main__":
    main()
