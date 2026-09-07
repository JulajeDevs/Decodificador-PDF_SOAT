import importlib
import sys
import types
import unittest


def cargar_mapfre():
    try:
        return importlib.import_module("IA_PDF").Mapfre
    except ModuleNotFoundError as error:
        if error.name not in {"pdfplumber", "pandas", "streamlit"}:
            raise

    pandas = types.ModuleType("pandas")
    pandas.read_excel = lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError())
    sys.modules.setdefault("pandas", pandas)
    sys.modules.setdefault("pdfplumber", types.ModuleType("pdfplumber"))
    sys.modules.setdefault("streamlit", types.ModuleType("streamlit"))
    sys.modules.pop("IA_PDF", None)
    return importlib.import_module("IA_PDF").Mapfre


Mapfre = cargar_mapfre()


class MapfreTests(unittest.TestCase):
    def test_certificados_actualizados(self):
        casos = (
            (
                "RTV93G",
                "3415123001526",
                "17/12/2023",
                "ROBIN JULIAN RIVERA GAVIRIA",
                "1065096009",
                "11.159.969",
                "12.477.717",
                "9.284.117",
                "VALOR PAGADO A LA FECHA",
                "NO AGOTADO",
            ),
            (
                "VCQ467",
                "3420123006160",
                "16/09/2024",
                "DELFIDO MARCELINO ANGULO TENORIO",
                "1089511269",
                "12.384.213",
                "12.384.213",
                "12.384.213",
                "VALOR PAGADO A LA FECHA POR GASTOS M\u00c9DICOS",
                "AGOTADO",
            ),
            (
                "VCX518",
                "1507123016194",
                "27/04/2024",
                "SULMA LIBORIA RIVERA",
                "31924647",
                "12.384.213",
                "200.000",
                "200.000",
                "VALOR PAGADO A LA FECHA POR GASTOS M\u00c9DICOS",
                "NO AGOTADO",
            ),
            (
                "ZDA211",
                "1503123001289",
                "20/01/2024",
                "EDILSON ALEXIS RIOS MU\u00d1OZ",
                "1121864831",
                "12.384.213",
                "12.965.397",
                "11.677.097",
                "TOTAL PAGADO A LA FECHA (263,13 UVT)",
                "NO AGOTADO",
            ),
            (
                "HJQ06G",
                "1507123015527",
                "02/10/2023",
                "ALBA INES CASTA\u00d1O SOTO",
                "1.010.134.938",
                "11.159.870",
                "11.159.870",
                "5.052.745",
                "VALOR PAGADO A LA FECHA POR GASTOS MEDICOS",
                "NO AGOTADO",
            ),
        )

        for (
            placa,
            poliza,
            fecha,
            nombre,
            identificacion,
            cobertura,
            reclamado,
            pagado,
            etiqueta_pago,
            estado,
        ) in casos:
            with self.subTest(placa=placa):
                texto = f"""
                MAPFRE SEGUROS GENERALES DE COLOMBIA S.A.
                Que el veh\u00edculo de placa {placa} se encuentra asegurado con la p\u00f3liza SOAT
                expedida por nuestra aseguradora bajo el n\u00famero {poliza}.
                FECHA DEL ACCIDENTE {fecha}
                ACCIDENTADO {nombre}
                IDENTIFICACI\u00d3N DE ACCIDENTADO C.C {identificacion}
                TOTAL, TOPE DE COBERTURA POR GASTOS M\u00c9DICOS (263,13 UVT) $ {cobertura}
                VALOR RECLAMADO A LA FECHA POR GASTOS M\u00c9DICOS $ {reclamado}
                {etiqueta_pago} $ {pagado}
                """

                data = Mapfre(texto)

                self.assertEqual(data["Placa"], placa)
                self.assertEqual(data["Numero Poliza"], poliza)
                self.assertEqual(data["Fecha Siniestro"], fecha)
                self.assertEqual(data["Nombres y Apellidos"], nombre)
                self.assertEqual(data["Identificaci\u00f3n"], identificacion)
                self.assertEqual(data["Cobertura"], f"${cobertura}")
                self.assertEqual(data["Valor Pagado"], f"${pagado}")
                self.assertEqual(data["Estado Cobertura"], estado)


if __name__ == "__main__":
    unittest.main()
