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

# --- CONFIGURACIÓN ---
CUIL = os.environ.get("CUIL")
PASSWORD = os.environ.get("PASSWORD")
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Direct-Link Activo")

def run_web_server():
    server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
    server.serve_forever()

# --- FUNCIÓN DE ENVÍO CON LINK DIRECTO ---
def enviar_telegram(texto, id_oferta, id_detalle, direccion):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    # Generamos el timestamp exacto que pide el ABC
    timestamp = int(time.time() * 1000)
    link_directo = f"https://misservicios.abc.gob.ar/actos.publicos.digitales/postulantes/?oferta={id_oferta}&detalle={id_detalle}&_t={timestamp}"
    
    botones = []
    # Botón 1: Postulación Directa
    botones.append([{"text": "✅ VER OFERTA", "url": link_directo}])
    
    # Botón 2: Mapa
    if direccion:
        query_mapa = f"{direccion}, Mar del Plata".replace(" ", "+")
        url_mapa = f"https://www.google.com/maps/search/?api=1&query={query_mapa}"
        botones.append([{"text": "📍 Ver Mapa", "url": url_mapa}])

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

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.set_ciphers("DEFAULT@SECLEVEL=1")
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

def monitorear():
    print("[*] Iniciando monitoreo con links directos...", flush=True)
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
            
            # Consulta
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
                        # El campo del detalle suele ser 'iddetalle' o 'idencabezado' en esta API
                        id_d = oferta.get("iddetalle") or oferta.get("idoferta") 
                        
                        if id_o not in ofertas_avisadas:
                            escuela = oferta.get('escuela', 'N/A')
                            direccion = oferta.get('domiciliodesempeno', '')
                            
                            msj = (f"🚨 **NUEVA JORNADA COMPLETA** 🚨\n\n"
                                   f"🏫 **Escuela:** {escuela}\n"
                                   f"📍 **Dirección:** {direccion}\n"
                                   f"📋 **ID Oferta:** `{id_o}`")
                            
                            enviar_telegram(msj, id_o, id_d, direccion)
                            ofertas_avisadas.add(id_o)
                            
            print("[*] Revisión OK.", flush=True)
        except Exception as e:
            print(f"[-] Error: {e}", flush=True)
            
        time.sleep(900)

if __name__ == "__main__":
    threading.Thread(target=monitorear, daemon=True).start()
    run_web_server()
