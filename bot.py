import os
import ssl
import requests
import urllib3
import time
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CARGA DE VARIABLES DE ENTORNO ---
CUIL = os.environ.get("CUIL")
PASSWORD = os.environ.get("PASSWORD")
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- SERVIDOR WEB PARA RENDER ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Modernizado Activo")

def run_web_server():
    server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
    server.serve_forever()

# --- ENVÍO DE TELEGRAM CON BOTONES ---
def enviar_telegram(texto, escuela=None, direccion=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    # Creamos los botones interactivos
    botones = []
    
    # Botón para postularse
    botones.append([{"text": "📝 Ir a Postularse", "url": "https://misservicios.abc.gob.ar/actos.publicos.digitales/"}])
    
    # Botón para ver en el mapa (si hay dirección)
    if direccion:
        query_mapa = f"{direccion}, Mar del Plata, Buenos Aires".replace(" ", "+")
        url_mapa = f"https://www.google.com/maps/search/?api=1&query={query_mapa}"
        botones.append([{"text": "📍 Ver Ubicación en Mapa", "url": url_mapa}])

    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({"inline_keyboard": botones})
    }
    
    try:
        requests.post(url, json=payload)
    except:
        pass

# --- CONFIGURACIÓN DE CONEXIÓN SEGURA ---
class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.set_ciphers("DEFAULT@SECLEVEL=1")
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

# --- MONITOREO PRINCIPAL ---
def monitorear():
    print("[*] Iniciando monitoreo modernizado...", flush=True)
    enviar_telegram("🚀 **Bot de Monitoreo Actualizado**\nAhora con botones de acceso rápido y mayor seguridad.")
    
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
            
            # Consulta APD
            url_solr = "https://servicios3.abc.gob.ar/valoracion.docente/api/apd.oferta.encabezado/select"
            params = {"q": 'descdistrito:"GENERAL PUEYRREDON" AND estado:"Publicada"', "rows": "1000", "wt": "json"}
            r = session.get(url_solr, params=params, verify=False)
            
            if r.status_code == 200:
                docs = r.json().get("response", {}).get("docs", [])
                for oferta in docs:
                    cargo = str(oferta.get("cargo", "")).upper()
                    jornada = str(oferta.get("jornada", "")).upper()
                    
                    if "MAESTRO DE GRADO" in cargo and jornada == "JC":
                        id_o = oferta.get("idoferta")
                        if id_o not in ofertas_avisadas:
                            escuela = oferta.get('escuela', 'N/A')
                            direccion = oferta.get('domiciliodesempeno', '')
                            
                            msj = (f"🚨 **¡OFERTA DE JORNADA COMPLETA!** 🚨\n\n"
                                   f"🏫 **Escuela:** {escuela}\n"
                                   f"📍 **Dirección:** {direccion}\n"
                                   f"📅 **Toma:** {oferta.get('tomaposesion', '')[:10]}")
                            
                            enviar_telegram(msj, escuela, direccion)
                            ofertas_avisadas.add(id_o)
                            
            print("[*] Revisión exitosa.", flush=True)
        except Exception as e:
            print(f"[-] Error en bucle: {e}", flush=True)
            
        time.sleep(1800) # 30 min

if __name__ == "__main__":
    threading.Thread(target=monitorear, daemon=True).start()
    run_web_server()
