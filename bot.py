import ssl
import requests
import urllib3
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# CONFIGURACIÓN (TUS DATOS)
# ==========================================
CUIL = "REMOVED"
PASSWORD = "REMOVED"
TELEGRAM_TOKEN = "REMOVED"
TELEGRAM_CHAT_ID = "REMOVED"
# ==========================================

# --- SERVIDOR WEB DE FACHADA PARA RENDER ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot activo")

def run_web_server():
    server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
    server.serve_forever()

# --- LÓGICA DEL BOT ---
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except:
        pass

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.set_ciphers("DEFAULT@SECLEVEL=1")
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

def monitorear():
    print("[*] Bot iniciado en Render (Free Tier)", flush=True)
    enviar_telegram("✅ **Bot activado en Render.**\nMonitoreo 24/7 en marcha.")
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
            
            # Buscar
            url_solr = "https://servicios3.abc.gob.ar/valoracion.docente/api/apd.oferta.encabezado/select"
            params = {"q": 'descdistrito:"GENERAL PUEYRREDON" AND estado:"Publicada"', "rows": "1000", "wt": "json"}
            r = session.get(url_solr, params=params, verify=False)
            if r.status_code == 200:
                for oferta in r.json().get("response", {}).get("docs", []):
                    cargo = str(oferta.get("cargo", "")).upper()
                    jornada = str(oferta.get("jornada", "")).upper()
                    if "MAESTRO DE GRADO" in cargo and jornada == "JC":
                        id_o = oferta.get("idoferta")
                        if id_o not in ofertas_avisadas:
                            msg = f"🚨 **NUEVO CARGO 8HS**\nEscuela: {oferta.get('escuela')}\nDir: {oferta.get('domiciliodesempeno')}"
                            enviar_telegram(msg)
                            ofertas_avisadas.add(id_o)
            print("[*] Vuelta de monitoreo completa.", flush=True)
        except Exception as e:
            print(f"[-] Error: {e}", flush=True)
        time.sleep(1800)

if __name__ == "__main__":
    # Corremos el bot en un hilo y el servidor web en otro
    threading.Thread(target=monitorear, daemon=True).start()
    run_web_server()
