import re
import pdfplumber
import pandas as pd
import streamlit as st
from io import BytesIO

# Cargar tipos de documentos
try:
    identificacion = pd.read_excel("Tipo_Documentos.xlsx")
    tipos_identificacion = identificacion["TipoDocumento"].tolist()
except FileNotFoundError:
    st.error("No se encontró el archivo 'Tipo_Documentos.xlsx'. Asegúrate de incluirlo.")
    tipos_identificacion = []

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

def seg_mundial(text):
    data = {
        "Aseguradora": "Seguros Mundial",
        "Nombres y Apellidos": "No encontrado",
        "Numero de Poliza": "No encontrado",
        "Fecha Siniestro": "No encontrado",
        "Estado Cobertura": "No encontrado",
        "Cobertura": "No encontrado",
        "Saldo Disponible": "No encontrado"
    }

    # --- CASO 1: CERTIFICADO SIN RECLAMACIONES ---
    if "no se identifican reclamaciones" in text.lower():
        data["Estado Cobertura"] = "SIN RECLAMACIONES"
        
        date_match = re.search(r"fecha\s+de\s+accidente\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
        if date_match:
            data["Fecha Siniestro"] = date_match.group(1)
            
        id_match = re.search(r"documento\s+([A-Z]{2}-?\d+)", text, re.IGNORECASE)
        if id_match:
            data["Numero de Documento"] = id_match.group(1)
            
        placa_match = re.search(r"placas\s+([A-Z0-9]+)", text, re.IGNORECASE)
        if placa_match:
             pass

        return data

    # --- CASO 2: CERTIFICADO CON TABLA DE PAGOS ---
    lines = text.split('\n')
    found_medical_expenses = False

    for line in lines:
        clean_line = re.sub(r'[",]', ' ', line).strip()
        
        if 'GASTOS MEDICOS' in clean_line.upper():
            found_medical_expenses = True
            
            pattern = re.compile(
                r"(?P<nombre>.+?)\s+"                 
                r"GASTOS\s+MEDICOS\s+"                
                r"(?P<fecha>\d{2}/\d{2}/\d{4})\s+"    
                r"(?P<info_intermedia>.*?)\s+"        
                r"(?P<estado>COBERTURA(?:\s+NO)?(?:\s+AGOTADA)?)" 
                r"(?P<resto>.*)", 
                re.IGNORECASE
            )
            
            match = pattern.search(clean_line)
            
            if match:
                raw_name = match.group("nombre").strip()
                raw_name = re.sub(r'^SEGUROS\s+MUNDIAL\s*', '', raw_name, flags=re.IGNORECASE).strip()
                data["Nombres y Apellidos"] = raw_name
                
                data["Fecha Siniestro"] = match.group("fecha").strip()
                
                info_intermedia = match.group("info_intermedia").strip()
                policy_search = re.search(r"([\d\-]{6,})", info_intermedia)
                if policy_search:
                     data["Numero de Poliza"] = policy_search.group(1)
                else:
                     data["Numero de Poliza"] = info_intermedia 
                
                status_raw = match.group("estado").strip().upper()
                if "NO" in status_raw:
                    data["Estado Cobertura"] = "NO AGOTADO"
                else:
                    data["Estado Cobertura"] = "AGOTADO"
                
                valor_raw = match.group("resto").strip()
                
                if valor_raw:
                    amounts = re.findall(r'\$\s*[\d\.,\s]+(?=(?:\$|$))', valor_raw)
                    clean_amounts = []
                    for amt in amounts:
                        amt_clean = amt.replace('$', '').strip()
                        amt_clean = re.sub(r'[\s,]+00$', '', amt_clean)
                        clean_amounts.append(f"$ {amt_clean}")
                    
                    if len(clean_amounts) > 0:
                        data["Cobertura"] = clean_amounts[0]
                        
                    if len(clean_amounts) > 1:
                        saldo_str = clean_amounts[1]
                        saldo_val = re.sub(r'[^\d]', '', saldo_str)
                        try:
                            if int(saldo_val) > 0:
                                data["Saldo Disponible"] = saldo_str
                            else:
                                data["Saldo Disponible"] = "No encontrado"
                        except:
                            data["Saldo Disponible"] = saldo_str
                    else:
                         data["Saldo Disponible"] = "No encontrado"
            else:
                st.warning(f"⚠️ Fila 'GASTOS MEDICOS' detectada pero con formato inusual: {clean_line}")
            
            break
            
    if not found_medical_expenses:
        header_policy = re.search(r"póliza.*?(\d{13,})", text, re.IGNORECASE)
        if header_policy:
             data["Numero de Poliza"] = header_policy.group(1)

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
def extract_data(text, pdf_file):
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
        data = seg_mundial(text)
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
                    # Es importante leer desde el inicio
                    uploaded_file.seek(0)
                    with pdfplumber.open(uploaded_file) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                    
                    if not text.strip():
                        st.warning(f"El archivo {uploaded_file.name} no contiene texto extraible o es una imagen escaneada.")
                        continue
                    
                    data = extract_data(text, uploaded_file.name)
                    results.append(data)
                    
                except Exception as e:
                    st.error(f"Error procesando {uploaded_file.name}: {str(e)}")
                    errors.append(uploaded_file.name)
            
            st.session_state["results_df"] = pd.DataFrame(results) if results else None
            st.session_state["processing_errors"] = errors
            st.session_state["processed_batch_id"] = current_batch_id 
            
            progress_bar.empty()
            status_text.text("Proceso completado!")
                
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
        
        # Recuperar y mostrar Errores
        if "processing_errors" in st.session_state and st.session_state["processing_errors"]:
            st.warning(f"Archivos con errores: {', '.join(st.session_state['processing_errors'])}")

if __name__ == "__main__":
    main()