# 📄 Procesador Automático de Certificaciones SOAT a Excel

## 🚀 Descripción del Proyecto

Esta herramienta es una aplicación web construida con **Streamlit** y **Python** diseñada para automatizar la tediosa tarea de extraer información clave de documentos PDF generados por diversas entidades prestadoras de salud (certificaciones, informes de agotamiento de SOAT, etc.).

El objetivo principal es permitir a los colaboradores subir múltiples archivos PDF a la vez, procesarlos automáticamente aplicando reglas específicas para cada aseguradora, y consolidar todos los datos estructurados (nombres, identificación, póliza, estado de cobertura, etc.) en un único archivo de **Excel (.xlsx)** descargable.

---

## ✨ Características Principales

* **Interfaz Gráfica (GUI):** Interfaz web intuitiva y fácil de usar, gracias a Streamlit.

* **Procesamiento por Lotes:** Capacidad para cargar y procesar múltiples archivos PDF simultáneamente.

* **Extracción Inteligente:** Utiliza expresiones regulares (`re`) y la librería `pdfplumber` para localizar y extraer datos específicos de diferentes formatos de documentos.

* **Soporte Multi-Entidad:** Mantiene funciones de extracción dedicadas para documentos de diferentes aseguradoras (ver listado abajo).

* **Salida Unificada:** Exporta todos los resultados a un solo archivo Excel con columnas estandarizadas, facilitando el análisis y la integración de datos.

---

## 🛠️ Requisitos e Instalación

### 1. Requisitos Técnicos

Asegúrate de tener instalado **Python 3.8+** en tu sistema.

### 2. Archivo de Datos de Soporte (Crucial)

El proyecto requiere un archivo auxiliar llamado **`Tipo_Documentos.xlsx`** en el mismo directorio del script. Este archivo debe contener los códigos de los tipos de identificación válidos para Colombia (ej. CC, TI, CE, AS, MS, etc.) en una columna nombrada `TipoDocumento`.

### 3. Librerías de Python Utilizadas

El proyecto fue desarrollado utilizando las siguientes librerías clave, que gestionan la interfaz, la lectura de archivos y la manipulación de datos:

| Librería | Propósito |
| :--- | :--- |
| **Streamlit** | Creación de la interfaz de usuario web interactiva. |
| **pandas** | Estructuras de datos (DataFrames) para unificar y manipular la información extraída. |
| **pdfplumber** | Extracción robusta de texto y datos de documentos PDF. |
| **xlsxwriter** | Motor esencial utilizado por `pandas` para generar y escribir el archivo final `.xlsx`. |
| **openpyxl** | Motor de soporte utilizado por `pandas` para la manipulación general de archivos Excel. |

### 4. Instalación de Dependencias

Puedes instalar todas las librerías necesarias ejecutando el siguiente comando:

```bash
pip install -r requirements.txt
```

(Nota: Este comando asume que ya has generado o creado el archivo `requirements.txt`.)

## 📋 Entidades SOAT Soportadas
El script soat_processor.py incluye lógica de extracción personalizada para los documentos de las siguientes entidades:

- MAPFRE (SOAT Certificaciones)

- PREVISORA S.A.

- SURAMERICANA S.A. (SURA)

- HDI SEGUROS COLOMBIA

- AXA COLPATRIA SEGUROS

- SEGUROS BOLIVAR S.A.

- SEGUROS MUNDIAL

- SEGUROS DEL ESTADO S.A.

- ASEGURADORA SOLIDARIA DE COLOMBIA

- LLAC (Indemnizaciones)

## 💻 Uso de la Aplicación
Asegúrate de que los archivos `soat_processor.py`, `Tipo_Documentos.xlsx` y `requirements.txt` estén en la misma carpeta.

Ejecuta la aplicación usando Streamlit:

```Bash
streamlit run soat_processor.py
```

Se abrirá una pestaña en tu navegador web.

Carga los PDFs: Haz clic en el botón __"Sube tus archivos PDF"__ y selecciona todos los documentos SOAT que deseas procesar.

Revisa y Descarga: La aplicación mostrará una barra de progreso mientras procesa cada archivo. Una vez finalizado, aparecerá una tabla de previsualización y un botón para __"Descargar Excel Consolidado"__.

