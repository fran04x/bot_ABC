import os
import ssl
import requests
import urllib3
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN ---
CUIL = os.environ.get("CUIL")
PASSWORD = os.environ.get("PASSWORD")
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Intelligence-Mode Activo")

def run_web_server():
    server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
    server.serve_forever()

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.set_ciphers("DEFAULT@SECLEVEL=1")
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

# --- FUNCIÓN PARA OBTENER EL RANKING ---
def obtener_top_postulantes(session, id_oferta):
    url_postulantes = "https://servicios3.abc.gob.ar/valoracion.docente/api/apd.oferta.postulante/select"
    params = {
        "q": f"idoferta:{id_oferta}",
        "sort": "puntaje desc",
        "rows": "3",
        "wt": "json"
    }
    try:
        r = session.get(url_postulantes, params=params, verify=False)
        if r.status_code == 200:
            postulantes = r.json().get("response", {}).get("docs", [])
            if not postulantes:
                return "_Sin postulantes aún_"
            
            resumen = ""
            for i, p in enumerate(postulantes, 1):
                nombre = f"{p.get('apellido', '')} {p.get('nombre', '')}".title()
                puntaje = p.get('puntaje', '0.00')
                vuelta = p.get('numeroVuelta', '1')
                prioridad = p.get('prioridadoferta', '-')
                resumen += f"  {i}º {nombre} | *{puntaje} pts* (V:{vuelta} P:{prioridad})\n"
            return resumen
    except:
        return "_Error al cargar ranking_"
    return "_Sin datos_"

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload)
    except:
        pass

def monitorear():
    print("[*] Monitoreo con Ranking de Postulantes iniciado...", flush=True)
    ofertas_avisadas = set()
    
    while True:
        session = requests.Session()
        session.mount('https://', TLSAdapter())
        session.headers.update({'User-Agent': 'Mozilla/5.0'})
        
        try:
            # Login
            login_url = "https://login.abc.gob.ar/nidp/idff/sso?sid=2&sid=2"
            payload = {'option': 'credential', 'target': 'https://menu.abc.gob.ar/', 'Ecom_User_ID': CUIL, 'Ecom_Password': PASSWORD}
            session.post(login_url, data=payload, verify=False)
            
            # Consulta Ofertas
            url_solr = "https://servicios3.abc.gob.ar/valoracion.docente/api/apd.oferta.encabezado/select"
            params = {"q": 'descdistrito:"GENERAL PUEYRREDON" AND estado:"Designada"', "rows": "1000", "wt": "json"}
            r = session.get(url_solr, params=params, verify=False)
            
            if r.status_code == 200:
                docs = r.json().get("response", {}).get("docs", [])
                nuevos = [o for o in docs if "MAESTRO DE GRADO" in str(o.get("cargo","")).upper() and str(o.get("jornada","")).upper() == "JC"]
                
                # Filtrar solo los que no avisamos
                nuevos_reales = []
                for n in nuevos:
                    if n.get("idoferta") not in ofertas_avisadas:
                        nuevos_reales.append(n)
                        ofertas_avisadas.add(n.get("idoferta"))

                if nuevos_reales:
                    cuerpo = "🚨 **RANKING DE JORNADA COMPLETA** 🚨\n\n"
                    ts = int(time.time() * 1000)
                    
                    for info in nuevos_reales:
                        id_o = info.get('idoferta')
                        id_d = info.get('iddetalle') or id_o
                        
                        # Buscamos el Top 3 para esta escuela
                        ranking = obtener_top_postulantes(session, id_o)
                        
                        link = f"https://misservicios.abc.gob.ar/actos.publicos.digitales/postulantes/?oferta={id_o}&detalle={id_d}&_t={ts}"
                        
                        cuerpo += f"🏫 **Escuela:** {info.get('escuela')}\n"
                        cuerpo += f"📚 **Área:** `{info.get('cargo')}`\n"
                        cuerpo += f"👥 **Curso/Div:** {info.get('curso')} - {info.get('division')}\n"
                        cuerpo += f"🏆 **Top 3 Candidatos:**\n{ranking}"
                        cuerpo += f"🔗 [CLIC AQUÍ PARA POSTULARSE]({link})\n"
                        cuerpo += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                    
                    enviar_telegram(cuerpo)
            print("[*] Vuelta de monitoreo completa.", flush=True)
        except Exception as e:
            print(f"[-] Error: {e}", flush=True)
        
        time.sleep(900)

if __name__ == "__main__":
    threading.Thread(target=monitorear, daemon=True).start()
    run_web_server()
