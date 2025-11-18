import re
import pdfplumber
import pandas as pd
import streamlit as st
import gc
from io import BytesIO

# Cargar tipos de documentos
try:
    identificacion = pd.read_excel("Tipo_Documentos.xlsx")
    tipos_identificacion = identificacion["TipoDocumento"].tolist()
except FileNotFoundError:
    tipos_identificacion = ["CC", "TI", "CE", "RC", "PA", "AS", "MS", "NU"]

# --- FUNCIONES DE EXTRACCIÓN POR ASEGURADORA ---

def Mapfre(text):
    data = {"Aseguradora": "Mapfre"}
    names_match = re.search(r"ACCIDENTADO\s+([\w\sÁÉÍÓÚÑáéíóúñ]+)\s+IDENTIFICACIÓN DE ACCIDENTADO", text, re.DOTALL)
    data["Nombres y Apellidos"] = names_match.group(1).strip() if names_match else None
    
    id_match = re.search(r"IDENTIFICACIÓN DE ACCIDENTADO\s*(?:C\.?C\s*)?([\d\.]+)", text)
    data["Identificación"] = id_match.group(1) if id_match else None
        
    policy_match = re.search(r"p[oó]liza\s+SOAT\s+expedida\s+por\s+(?:nuestra\s+aseguradora|nuestra\s+entidad)\s+bajo\s+el\s+n[uú]mero\s+(\d+)", text, re.IGNORECASE)
    data["Numero de Poliza"] = policy_match.group(1) if policy_match else None
        
    total_paid_match = re.search(r"(?:TOTAL|VALOR|TOTAL,)\s+(?:LIQUIDADO|PAGADO|CANCELADO|RECLAMADO)[^$]*\$\s*([\d\.,]+)", text, re.IGNORECASE)
    if total_paid_match:
        valor = total_paid_match.group(1)
        data["Valor Total Pagado"] = valor
    else:
        data["Valor Total Pagado"] = None
    
    coverage_match = re.search(r"TOPE\s+DE\s+COBERTURA[^$]+\$\s*([\d\.,]+)", text, re.IGNORECASE)
    if coverage_match:
        cobertura = coverage_match.group(1)
        data["Cobertura"] = cobertura
    else:
        data["Cobertura"] = None
    
    if data["Valor Total Pagado"] and data["Cobertura"]:
        valor_total = int(data["Valor Total Pagado"].replace(".", ""))
        total_cobertura = int(data["Cobertura"].replace(".", ""))
        if valor_total < total_cobertura:
            data["Estado Cobertura"] = "NO AGOTADO"
        else:
            data["Estado Cobertura"] = "AGOTADO"
    else:
        data["Estado Cobertura"] = "Desconocido"
    
    date_match = re.search(r"FECHA DEL ACCIDENTE\s+(\d{2}/\d{2}/\d{4})", text)
    data["Fecha Siniestro"] = date_match.group(1).strip() if date_match else "No encontrado"
        
    return data

def previsora(text):
    data = {"Aseguradora": "Previsora"}
    match_new_id = re.search(r"(AS|ERI|[A-Z]{2})\s*(\d+[A-Z]\d+|\d{8}[A-Z]{2})", text)
    if match_new_id:
        data["Tipo Documento"] = match_new_id.group(1).strip().upper()
        data["Numero de Documento"] = match_new_id.group(2).strip()
    else:
        match_names_old = re.search(r"\b(" + "|".join(tipos_identificacion) + r")\s+(\d{5,15})\s+([A-Za-zÁÉÍÓÚÑáéíóúñ0-9\s]+?)\s+\d{2}-\d{2}-\d{4}", text, re.DOTALL)
        
        if match_names_old:
            data["Nombres y Apellidos"] = match_names_old.group(3).strip()
            data["Tipo Documento"] = match_names_old.group(1).strip().upper()
            data["Numero de Documento"] = match_names_old.group(2).strip()
        else:
            match_ven = re.search(r"ACCIDENTADO.*?(MS|AS|CC|TI)\s+(VEN\d+)\s+([A-ZÁÉÍÓÚÑ\s]+?)\s+\d{2}-\d{2}-\d{4}", text, re.DOTALL) 
            if match_ven:
                data["Nombres y Apellidos"] = match_ven.group(3).strip()
                data["Numero de Documento"] = match_ven.group(2).strip()
                doc_match = re.search(r"\b(" + "|".join(map(re.escape, tipos_identificacion)) + r")\b", match_ven.group(0))
                if doc_match:
                    data["Tipo Documento"] = doc_match.group(1).strip().upper()
                else:
                    data["Tipo Documento"] = "No encontrado"
            else:
                tipos_regex= "|".join(map(re.escape, tipos_identificacion))
                match_split_n = re.search(
                    r"ACCIDENTADO(?:\s+VÍCTIMA\s+SINIESTRO)?\s*\n"
                    r"(?P<nombre1>[A-ZÁÉÍÓÚÑ\s]+)"
                    r"(?:\n(?P<nombre2>(?!(" + tipos_regex + r")\b)[A-ZÁÉÍÓÚÑ\s]+))?"
                    r"\n\s*(?P<tipo>(" + tipos_regex + r"))\s*(?P<num>\d{5,15})"
                    r"(?:\s*\n\s*(?P<nombre3>[A-ZÁÉÍÓÚÑ\s]+))?",
                    text, re.DOTALL
                )
                if match_split_n:
                    nombre = match_split_n.group("nombre1").strip()
                    if match_split_n.group("nombre2"):
                            nombre += " " + match_split_n.group("nombre2").strip()
                    if match_split_n.group("nombre3"):
                        nombre += " " + match_split_n.group("nombre3").strip()
                    data["Nombres y Apellidos"] = nombre
                    data["Tipo Documento"] = match_split_n.group("tipo").strip().upper()
                    data["Numero de Documento"] = match_split_n.group("num").strip()
                else:
                    data.update({"Nombres y Apellidos": "No encontrado", "Tipo Documento": "No encontrado", "Numero de Documento": "No encontrado"})
    
    match_policy = re.search(r"PÓLIZA DESDE HASTA PLACA\s*(\d{13,16})", text)
    if match_policy:
        data["Numero de Poliza"] = match_policy.group(1).strip()
    else:
        data["Numero de Poliza"] = "No encontrado"
    
    if "NO HA AGOTADO" in text:
        data["Cobertura"] = "NO HA AGOTADO"
    elif "HA AGOTADO" in text:
        data["Cobertura"] = "HA AGOTADO"
    else:
        data["Cobertura"] = "No encontrado"
    
    date_match = re.search("(\d{2}-\d{2}-\d{4})(?:\s*\$|$)", text, re.MULTILINE)
    data["Fecha Siniestro"] = date_match.group(1).strip() if date_match else "No encontrado"
    
    return data

def sura(text):
    data = {"Aseguradora": "Sura"}
    tipos_id = "|".join(map(re.escape, tipos_identificacion))
    match_names = re.compile(rf"(?:Identificación\s+accidentado\s+.*?)?({tipos_id})\s+(\d+)\s+([^\d]+?)\s*\d{{2}}-\d{{2}}-\d{{4}}" ,re.DOTALL | re.IGNORECASE)
    
    match_names = match_names.search(text)
    if match_names:
        data["Nombres y Apellidos"] = match_names.group(3).strip()
        data["Tipo de documento"] = match_names.group(1)
        data["Identificación"] = match_names.group(2)
    else:
        data["Nombre y Apellidos"] = "No encontrado"
        data["Tipo de documento"] = "No identificado"
        data["Identificación"] = "No encontrado"
    
    policy_match = re.search(r"(\d{8,12})", text)
    data["Numero de Poliza"] = policy_match.group() if policy_match else "No encontrado"
    
    total_line_match = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s+UVT\s+(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s+(\d{1,3}(?:\.\d{3})*(?:,\d+)?)", text)
    if total_line_match:
        data["Cobertura"] = total_line_match.group(2)
        data["Valor total pagado"] = total_line_match.group(3)
    else:
        data["Cobertura"] = "No encontrado"
        data["Valor total pagado"] = "No encontrado"
    
    if "NO" in text and "AGOTADO" in text:
        data["Estado Cobertura"] = "NO AGOTADO"
    else:
        data["Estado Cobertura"] = "AGOTADO"
        
    date_match = re.search(rf"INFORMACIÓN DEL ACCIDENTADO.*?(?:Fecha\s*accidente\s*.*?|(?:{tipos_id})\s+\d+.*?)(\d{{2}}[-/]\d{{2}}[-/]\d{{4}})", text, re.IGNORECASE | re.DOTALL)
    data["Fecha Siniestro"] = date_match.group(1) if date_match else "No encontrado"
    
    return data

def hdi(text):
    data = {"Aseguradora": "HDI"}
    match_names = re.search(r"Nombre de la víctima:\s*([A-ZÁÉÍÓÚÑ ]+)", text, re.IGNORECASE)
    data["Nombres y Apellidos"] = match_names.group(1) if match_names else "No encontrado"
    match_id = re.search(r"Número Id víctima:\s*(\d+)", text, re.IGNORECASE)
    data["Identificacion"] = match_id.group(1).replace(".", "") if match_id else "No encontrado"
    policy_match = re.search(r"Póliza:\s*(\d+)", text, re.IGNORECASE)
    data["Numero Poliza"] = policy_match.group(1) if policy_match else "No encontrado"
    total_paid_match = re.search(r"(?:Valor\s*total\s*pagado\s*:|TOTAL PAGADO AMPARO)\s*\$\s*([\d.,]+)", text, re.IGNORECASE)
    data["Valor Total Pagado"] = total_paid_match.group(1) if total_paid_match else "No encontrado"
    date_match = re.search("(?i)Fecha\s*(?:de\s*)?accidente\s*:?\s*(\d{2}[-/]\d{2}[-/]\d{4})", text)
    data["Fecha Siniestro"] = date_match.group(1) if date_match else "No encontrado"
    return data

def indemnizaciones(text):
    data = {"Aseguradora": "Indemnizaciones"}
    name_match = re.search(r"(?:La señora|El señor)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]+),\s*identificad[ao] con", text, re.IGNORECASE)
    data["Nombres y Apellidos"] = name_match.group(1).strip() if name_match else "No encontrado"
    id_match= re.search(r"Cédula de\s+Ciudadanía[\s\n]*([\d\.,]+)", text, re.IGNORECASE)
    data["Identificacion"] = id_match.group(1).replace(".", "") if id_match else "No encontrado"
    policy_match = re.search(r"POLIZA SOAT No\.\s*(\d+)", text,re.IGNORECASE)
    data["Numero Poliza"] = policy_match.group(1) if policy_match else "No encontrado"
    no_present_match = re.search(r"NO HA PRESENTADO PAGOS POR CONCEPTOS DE GASTOS MEDICOS", text, re.IGNORECASE)
    data["Concepto Gastos"] = "NO HA PRESENTADO GASTOS MÉDICOS" if no_present_match else "No encontrado"
    return data

def bolivar(text):
    data = {"Aseguradora": "Seguros Bolivar"}
    name_match = re.search(r"([A-Z]{2,})\s+(\d+)\s+([A-ZÁÉÍÓÚÑ\s]+?)\s+\d{2}-\d{2}-\d{4}", text, re.IGNORECASE | re.DOTALL)
    if name_match:
        data["Nombres y Apellidos"] = name_match.group(3).strip()
        data["Identificación"] = name_match.group(2).strip()
        data["Tipo Identificación"] = name_match.group(1).strip()
    else:
        data.update({"Nombres y Apellidos": "No Encontrado", "identificacion":"No Encontrado", "Tipo Identificación": "No Encontrado"})
    
    policy_match = re.search(r"(?:Póliza\s+Número.*?(\d{13,})|(?:No\.|numero)\s*(\d+))", text, re.IGNORECASE | re.DOTALL)
    data["Numero Poliza"] = policy_match.group(1) if policy_match else "No encontrado"
    
    total_line_match = re.search(r"(\d+\.\d+)\s+\$\s+([\d.]+)\s+\$\s+([\d.]+)", text)
    if total_line_match:
        data["Cobertura"] = total_line_match.group(2)
        data["Valor Pagado"] = total_line_match.group(3)
        valor_pagado = int(data["Valor Pagado"].replace(".", ""))
        cobertura = int(data["Cobertura"].replace(".", ""))
        data["Estado Cobertura"] = "AGOTADO" if valor_pagado >= cobertura else "NO AGOTADO"
    else:
        data["Cobertura"] = "No encontrado"
        data["Valor Pagado"] = "No encontrado"
        data["Estado Cobertura"] = "Desconocido"
    
    match_date = re.search(r"Fecha Accidente.*?(\d{2}-\d{2}-\d{4})", text, re.DOTALL)
    data["Fecha Siniestro"] = match_date.group(1) if match_date else "No encontrado"
    return data

def seg_mundial(text, pdf=None):
    data = {
        "Aseguradora": "Seguros Mundial",
        "Nombres y Apellidos": "No encontrado",
        "Numero de Poliza": "No encontrado",
        "Fecha Siniestro": "No encontrado",
        "Estado Cobertura": "No encontrado",
        "Cobertura": "No encontrado",
        "Saldo Disponible": "No encontrado"
    }
    
    found_in_table = False

    # --- ESTRATEGIA 1: EXTRACCIÓN POR TABLAS ---
    if pdf:
        try:
            for page in pdf.pages:
                tables = page.extract_tables()
                
                for table in tables:
                    header_idx = -1
                    col_indices = {}
                    
                    for i, row in enumerate(table):
                        row_clean = [str(c).upper().replace('\n', ' ') if c else "" for c in row]
                        
                        if "AFECTADO" in row_clean and "AMPARO" in row_clean:
                            header_idx = i
                            # Mapear columnas dinámicamente
                            try:
                                col_indices["AFECTADO"] = row_clean.index("AFECTADO")
                                col_indices["AMPARO"] = row_clean.index("AMPARO")
                                # Buscar otras columnas aproximadas
                                for idx, col_name in enumerate(row_clean):
                                    if "FECHA" in col_name and "ACCIDENTE" in col_name: col_indices["FECHA"] = idx
                                    if "POLIZA" in col_name: col_indices["POLIZA"] = idx
                                    if "ESTADO" in col_name: col_indices["ESTADO"] = idx
                                    if "TOPE" in col_name: col_indices["TOPE"] = idx
                                    if "SALDO" in col_name: col_indices["SALDO"] = idx
                            except:
                                pass
                            break
                    
                    if header_idx != -1:
                        for row in table[header_idx+1:]:
                            idx_afectado = col_indices.get("AFECTADO", 0)
                            idx_amparo = col_indices.get("AMPARO", 1)
                            
                            if len(row) > idx_amparo:
                                amparo_val = str(row[idx_amparo]).upper() if row[idx_amparo] else ""
                                if "GASTOS MEDICOS" in amparo_val:
                                    # --- EXTRACCIÓN DEL NOMBRE (CELDA COMPLETA) ---
                                    raw_name = row[idx_afectado]
                                    if raw_name:
                                        full_name = raw_name.replace('\n', ' ').strip()
                                        full_name = re.sub(r'^SEGUROS\s+MUNDIAL\s*', '', full_name, flags=re.IGNORECASE).strip()
                                        data["Nombres y Apellidos"] = full_name
                                        found_in_table = True

                                    # --- EXTRACCIÓN DEL RESTO DE DATOS (MISMA FILA) ---
                                    # Fecha
                                    if "FECHA" in col_indices and len(row) > col_indices["FECHA"]:
                                        val = row[col_indices["FECHA"]]
                                        if val: data["Fecha Siniestro"] = val.replace('\n', ' ').strip()
                                    
                                    # Póliza
                                    if "POLIZA" in col_indices and len(row) > col_indices["POLIZA"]:
                                        val = row[col_indices["POLIZA"]]
                                        if val: data["Numero de Poliza"] = val.replace('\n', ' ').strip()
                                    
                                    # Cobertura (Tope)
                                    if "TOPE" in col_indices and len(row) > col_indices["TOPE"]:
                                        val = row[col_indices["TOPE"]]
                                        if val: 
                                            clean_val = val.replace('\n', ' ').strip()
                                            clean_val = re.sub(r',00$', '', clean_val)
                                            data["Cobertura"] = clean_val

                                    # Estado
                                    if "ESTADO" in col_indices and len(row) > col_indices["ESTADO"]:
                                        val = str(row[col_indices["ESTADO"]]).upper()
                                        if val:
                                            if "NO" in val and "AGOTADA" in val:
                                                data["Estado Cobertura"] = "NO AGOTADO"
                                            elif "AGOTADA" in val:
                                                data["Estado Cobertura"] = "AGOTADO"
                                    
                                    if "SALDO" in col_indices and len(row) > col_indices["SALDO"]:
                                        val = row[col_indices["SALDO"]]
                                        if val:
                                            try:
                                                saldo_clean = val.replace('\n', ' ').strip()
                                                # Validar si es número positivo
                                                num_chk = int(re.sub(r'[^\d]', '', saldo_clean))
                                                
                                                if num_chk > 0: # Si es mayor a 0, se guarda
                                                    data["Saldo Disponible"] = saldo_clean
                                                else: # Si es 0 o negativo, "No encontrado"
                                                    data["Saldo Disponible"] = "No encontrado"
                                            except:
                                                pass
                                    
                                    return data
        except Exception as e:
            pass

    # --- ESTRATEGIA 2: REGEX (FALLBACK) ---
    if not found_in_table:
        if "no se identifican reclamaciones" in text.lower():
            data["Estado Cobertura"] = "SIN RECLAMACIONES"
            date_match = re.search(r"fecha\s+de\s+accidente\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
            if date_match: data["Fecha Siniestro"] = date_match.group(1)
            header_name = re.search(r"Afectado\s*\n\s*([A-ZÁÉÍÓÚÑ\s]+?)(?=\n)", text, re.IGNORECASE)
            if header_name: data["Nombres y Apellidos"] = header_name.group(1).strip()
        else:
            header_policy = re.search(r"póliza.*?(\d{13,})", text, re.IGNORECASE)
            if header_policy: data["Numero de Poliza"] = header_policy.group(1)

    return data

def colpatria_axa(text):
    data = {"Aseguradora": "AXA Colpatria"}
    name_match = re.search(r"(?:Lesionado \(a\) :|AFECTADO / LESIONADO)\s+(.*)", text, re.IGNORECASE)
    data["Nombres y Apellidos"] = name_match.group(1).strip() if name_match else None
    type_id = re.search(r"Tipo ID Lesionado : (.*)", text, re.IGNORECASE)
    data["Tipo de identificación"] = type_id.group(1).strip() if type_id else "No econtrado"
    number_id = re.search(r"Numero de ID Lesionado : (.*)", text, re.IGNORECASE)
    data["Numero de identificación"] = number_id.group(1).strip() if number_id else "No encontrado"
    accident_date = re.search(r"(?:Fecha Ocurrencia :|FECHA OCURRENCIA SINIESTRO)\s+(.*)", text, re.IGNORECASE)
    data["Fecha de incidente"] = accident_date.group(1).strip() if accident_date else None
    
    policy_match = re.search(r"(?:No\. Póliza : (.*)|número\s+(.*?)(?=\s+placa))", text, re.IGNORECASE)
    policy_number = "No encontrado"
    if policy_match:
        if policy_match.group(1): policy_number = policy_match.group(1).strip()
        elif policy_match.group(2): policy_number = policy_match.group(2).strip()
    data["Numero de Poliza"] = policy_number

    status_match_new = re.search(r"COBERTURA AGOTADA\s+SI", text, re.IGNORECASE)
    if status_match_new:
        data["Estado de Cobertura"] = "AGOTADO"
    else:
        status_match_old = re.search(r"(AGOTADO|NO AGOTADO)", text, re.IGNORECASE)
        data["Estado de Cobertura"] = status_match_old.group(1).strip() if status_match_old else "No encontrado"
    return data

def seg_estados(text):
    data={"Aseguradora": "Seguros del Estado"}
    afectado_match= re.search(r"AFECTADO\s+(\d+)-([^\n]+)", text, re.IGNORECASE)
    if afectado_match:
        data["Numero ID"] = afectado_match.group(1)
        data["Nombre y Apellido"] = afectado_match.group(2)
    else:
        data["Nombre y Apellido"] = None
        data["Numero ID"] = None
    number_policy = re.search(r"No\.\s*(\d+)", text, re.IGNORECASE)
    data["Numero de Poliza"] = number_policy.group(1) if number_policy else None
    date = re.search(r"FECHA DE SINIESTRO\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    data["Fecha Siniestro"] = date.group(1) if date else None
    coverage = re.search(r"ESTADO Cobertura\s+(.*?)(?=\n|$)", text, re.IGNORECASE)
    data["Estado de Cobertura"] = coverage.group(1) if coverage else None
    return data

def solidaria(text):
    data ={"Aseguradora": "Aseguradora Solidaria"}
    id_name_match = re.search(r"(CC|TI|CE|PE|NIT|AS|DE|MS|CN)\s+(\d+)\s+([A-ZÁÉÍÓÚÑ\s]+?)\s+(\d{2}-\d{2}-\d{4})", text, re.IGNORECASE)
    if id_name_match:
        data["Nombre y Apellido"] = id_name_match.group(3).strip().title()
        data["Tipo ID"] = id_name_match.group(1).strip().upper()
        data["Numero ID"] = id_name_match.group(2).strip()
        data["Fecha de Siniestro"] = id_name_match.group(4).strip()
    else:
        data["Nombre y Apellido"] = None
        data["Tipo ID"] = None
        data["Numero ID"] = None
        data["Fecha de Siniestro"] = None
    
    coverage_match = re.search(r"Valor Disponible.*?(\bAGOTADO\b|\bNO AGOTADO\b)", text, re.DOTALL|re.IGNORECASE)
    data["Estado de Cobertura"] = coverage_match.group(1).strip() if coverage_match else None
    policy_match = re.search(r"Póliza Número\D+(\d+)", text)
    data["Numero de Poliza"] = policy_match.group(1).strip() if policy_match else None
    return data

# Extraction process 
def extract_data(text, pdf_file, pdf_obj=None):
    if re.search(r"MAPFRE SEGUROS GENERALES DE COLOMBIA", text, re.IGNORECASE):
        data = Mapfre(text)
        return {**data, "Nombre archivo": pdf_file}
    elif re.search(r"PREVISORA S.A.", text, re.IGNORECASE):
        data = previsora(text)
        return {**data, "Nombre archivo": pdf_file}
    elif re.search(r"SURAMERICANA S.A", text, re.IGNORECASE):
        data = sura(text)
        return {**data, "Nombre archivo": pdf_file}
    elif re.search(r"HDI SEGUROS COLOMBIA|CERTIFICADO DE AGOTAMIENTO DE COBERTURA", text, re.IGNORECASE):
        data = hdi(text)
        return {**data, "Nombre archivo": pdf_file}
    elif re.search(r"LLAC", text, re.IGNORECASE):
        data= indemnizaciones(text)
        return {**data, "Nombre archivo":pdf_file}
    elif re.search(r"SEGUROS\s+BOLIVAR\b.*?S\.A\.", text, re.IGNORECASE|re.DOTALL):
        data = bolivar(text)
        return {**data, "Nombre archivo":pdf_file}
    elif re.search(r"SEGUROS MUNDIAL", text, re.IGNORECASE):
        # AQUÍ ESTÁ EL CAMBIO CLAVE: Pasamos el objeto PDF
        data = seg_mundial(text, pdf_obj)
        return {**data, "Nombre archivo":pdf_file}
    elif re.search(r"AXA COLPATRIA SEGUROS", text, re.IGNORECASE):
        data = colpatria_axa(text)
        return {**data, "Nombre archivo":pdf_file}
    elif re.search(r"(?i)SEGUROS DEL ESTADO S\.A\.", text):
        data = seg_estados(text)
        return {**data, 'Nombre archivo':pdf_file}
    elif re.search(r"ASEGURADORA SOLIDARIA DE COLOMBIA", text):
        data = solidaria(text)
        return {**data, 'Nombre archivo':pdf_file}
    else:
        return {"Nombre archivo": pdf_file, "Error": "Aseguradora no identificada", "Aseguradora": "Desconocida"}

def main():
    st.title("Procesador de PDFs SOAT")
    st.write("Sube los archivos PDF para extraer la información")
    
    uploaded_files = st.file_uploader("Sube tus archivos PDF", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        # --- CACHÉ Y GESTIÓN DE ESTADO ---
        current_batch_id = sorted([f.name for f in uploaded_files])
        
        if "processed_batch_id" not in st.session_state or st.session_state["processed_batch_id"] != current_batch_id:
            
            results = []
            errors = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                try:
                    progress = (i + 1) / len(uploaded_files)
                    progress_bar.progress(progress)
                    status_text.text(f"Procesando archivo {i+1} de {len(uploaded_files)}: {uploaded_file.name}")
                    
                    text = ""
                    uploaded_file.seek(0)
                    with pdfplumber.open(uploaded_file) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                        
                        if not text.strip():
                            st.warning(f"El archivo {uploaded_file.name} no contiene texto extraible o es una imagen escaneada.")
                            continue
                        
                        data = extract_data(text, uploaded_file.name, pdf)
                        results.append(data)
                    
                    if i % 10 == 0:
                        gc.collect()

                except Exception as e:
                    st.error(f"Error procesando {uploaded_file.name}: {str(e)}")
                    errors.append(uploaded_file.name)
            
            st.session_state["results_df"] = pd.DataFrame(results) if results else None
            st.session_state["processing_errors"] = errors
            st.session_state["processed_batch_id"] = current_batch_id
            
            progress_bar.empty()
            status_text.text("Proceso completado!")
        
        # --- VISUALIZACIÓN ---
        
        if "results_df" in st.session_state and st.session_state["results_df"] is not None:
            df = st.session_state["results_df"]
            
            st.subheader("Vista previa de los datos")
            st.dataframe(df)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Datos SOAT')
            
            st.download_button(
                label="Descargar Excel",
                data=output.getvalue(),
                file_name="resultados_soat.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        if "processing_errors" in st.session_state and st.session_state["processing_errors"]:
            st.warning(f"Archivos con errores: {', '.join(st.session_state['processing_errors'])}")

if __name__ == "__main__":
    main()