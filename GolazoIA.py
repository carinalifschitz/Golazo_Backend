import asyncio
import json
import os
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from openai import OpenAI

# --- CONFIGURACIÓN DE CREDENCIALES ---
GROK_API_KEY = os.environ.get("GROK_API_KEY", "TU_API_KEY_DE_GROK")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "TU_API_KEY_DE_API_FOOTBALL")

client = OpenAI(
    api_key=GROK_API_KEY, 
    base_url="https://x.ai"
)

# --- VARIABLES DE CONTROL ---
BANCO_TRIVIAS = []
INDICE_INDIVIDUAL = {}
jugadores_esperando = []
salas_activas = {}
RANKING_GLOBAL = {}

app = FastAPI()

# ----------------------------------------------------------------
# CONEXIÓN CON API-FOOTBALL (apifootball.com)
# ----------------------------------------------------------------
def obtener_datos_futbol_real():
    url_base = "https://api-sports.io"
    headers = {
        "x-rapidapi-host": "v3.football.api-sports.io",
        "x-rapidapi-key": FOOTBALL_API_KEY
    }
    datos_futbol = {"goleadores": [], "estadios": [], "partidos_jugados": []}
    try:
        url_goleadores = f"{url_base}/players/topscorers?league=128&season=2026"
        res_goleadores = requests.get(url_goleadores, headers=headers, timeout=10).json()
        if "response" in res_goleadores:
            for item in res_goleadores["response"][:12]:
                player = item["player"]
                statistics = item["statistics"] if isinstance(item["statistics"], list) else item["statistics"]
                datos_futbol["goleadores"].append({
                    "nombre": player["name"],
                    "equipo": statistics["team"]["name"],
                    "goles": statistics["goals"]["total"],
                    "nacionalidad": player["nationality"]
                })
                
        url_equipos = f"{url_base}/teams?league=128&season=2026"
        res_equipos = requests.get(url_equipos, headers=headers, timeout=10).json()
        if "response" in res_equipos:
            for item in res_equipos["response"][:12]:
                team = item["team"]
                venue = item["venue"]
                datos_futbol["estadios"].append({
                    "equipo": team["name"],
                    "estadio_nombre": venue["name"],
                    "ciudad": venue["city"],
                    "capacidad": venue["capacity"]
                })

        url_fixtures = f"{url_base}/fixtures?league=128&season=2026&status=FT"
        res_fixtures = requests.get(url_fixtures, headers=headers, timeout=10).json()
        if "response" in res_fixtures:
            for item in res_fixtures["response"][-15:]:
                teams = item["teams"]
                goals = item["goals"]
                fixture_venue = item["fixture"]["venue"]
                datos_futbol["partidos_jugados"].append({
                    "local": teams["home"]["name"],
                    "visitante": teams["away"]["name"],
                    "goles_local": goals["home"],
                    "goles_visitante": goals["away"],
                    "estadio": fixture_venue["name"],
                    "ciudad": fixture_venue["city"]
                })
    except Exception as e:
        print(f"Error al recolectar datos de API-Football: {e}")
    return datos_futbol

async def generar_banco_trivias_ai():
    global BANCO_TRIVIAS
    print("Obteniendo estadísticas desde API-Football...")
    loop = asyncio.get_running_loop()
    contexto_futbol = await loop.run_in_executor(None, obtener_datos_futbol_real)
    print("Iniciando solicitud a Grok...")

    prompt_sistema = "Sos un experto en trivias de fútbol. Responde ÚNICAMENTE con un objeto JSON estructurado que contenga un array de exactamente 40 preguntas bajo la clave 'preguntas'. Sin bloques Markdown."
    prompt_usuario = f"Basándote en estos datos reales: {json.dumps(contexto_futbol, ensure_ascii=False)} Genera un array de exactamente 40 preguntas de trivia de fútbol con estructura: pregunta, opciones, correcta."
    
    try:
        completion = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="grok-beta", 
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": prompt_usuario}]
            )
        )
        datos_parseados = json.loads(completion.choices.message.content)
        if "preguntas" in datos_parseados:
            BANCO_TRIVIAS = datos_parseados["preguntas"]
            print(f"¡Éxito! Se inyectaron {len(BANCO_TRIVIAS)} preguntas.")
    except Exception as e:
        print(f"Fallo crítico en la generación de IA: {e}")
        BANCO_TRIVIAS = [{"pregunta": "¿Quién ganó el mundial de Qatar 2022?", "opciones": ["Argentina", "Francia", "Brasil"], "correcta": "Argentina"}]

# ----------------------------------------------------------------
# EVENTO DE INICIO DEL SERVIDOR
# ----------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    # Descarga las preguntas al encender el contenedor
    await generar_banco_trivias_ai()

# ----------------------------------------------------------------
# RUTA 1: SERVIR EL ARCHIVO HTML (PÁGINA WEB)
# ----------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def obtener_interfaz():
    # Buscamos el archivo index.html en la misma carpeta del proyecto
    ruta_html = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(ruta_html):
        with open(ruta_html, "r", encoding="utf-8") as archivo:
            return HTMLResponse(content=archivo.read(), status_code=200)
    return HTMLResponse(content="<h1>Error: No se encontró el archivo index.html en el servidor.</h1>", status_code=404)

# ----------------------------------------------------------------
# RUTA 2: PUNTO DE ENTRADA DEL WEBSOCKET (/ws)
# ----------------------------------------------------------------
@app.websocket("/ws")
async def endpoint_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            mensaje = await websocket.receive_text()
            datos = json.loads(mensaje)
            # Aquí procesas tus salas y mecánicas de juego pasadas...
            pass
    except WebSocketDisconnect:
        print("Un jugador se ha desconectado.")
