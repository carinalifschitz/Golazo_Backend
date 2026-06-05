import asyncio
import json
import os
import requests
from contextlib import asynccontextmanager
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

# Banco de emergencias obligatorio por si falla la API
BANCO_RESPALDO = [
    {"pregunta": "¿Quién ganó el mundial de Qatar 2022?", "opciones": ["Argentina", "Francia", "Brasil"], "correcta": "Argentina"},
    {"pregunta": "¿Quién es el máximo goleador de la Selección Argentina?", "opciones": ["Messi", "Maradona", "Batistuta"], "correcta": "Messi"},
    {"pregunta": "¿Cuál es el estadio de Boca Juniors?", "opciones": ["La Bombonera", "El Monumental", "El Cilindro"], "correcta": "La Bombonera"}
]

# ----------------------------------------------------------------
# CONEXIÓN CON API-FOOTBALL (apifootball.com)
# ----------------------------------------------------------------
def obtener_datos_futbol_real():
    # CORRECCIÓN 2: URL Base alineada con el Host de la API
    url_base = "https://v3.football.api-sports.io"
    headers = {
        "x-rapidapi-host": "v3.football.api-sports.io",
        "x-rapidapi-key": FOOTBALL_API_KEY
    }
    datos_futbol = {"goleadores": [], "estadios": [], "partidos_jugados": []}
    try:
        url_goleadores = f"{url_base}/players/topscorers?league=128&season=2026"
        res_goleadores = requests.get(url_goleadores, headers=headers, timeout=5).json()
        if "response" in res_goleadores:
            for item in res_goleadores["response"][:12]:
                player = item["player"]
                # CORRECCIÓN 1: statistics siempre llega como una LISTA desde API-Football
                stats_list = item["statistics"]
                stats = stats_list[0] if isinstance(stats_list, list) and len(stats_list) > 0 else stats_list
                
                datos_futbol["goleadores"].append({
                    "nombre": player["name"],
                    "equipo": stats["team"]["name"] if "team" in stats else "Desconocido",
                    "goles": stats["goals"]["total"] if "goals" in stats else 0,
                    "nacionalidad": player["nationality"]
                })
                
        url_equipos = f"{url_base}/teams?league=128&season=2026"
        res_equipos = requests.get(url_equipos, headers=headers, timeout=5).json()
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
        res_fixtures = requests.get(url_fixtures, headers=headers, timeout=5).json()
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
        print(f"Error controlado al recolectar datos de API-Football: {e}")
    return datos_futbol

async def generar_banco_trivias_ai():
    global BANCO_TRIVIAS
    try:
        print("Obteniendo estadísticas desde API-Football...")
        loop = asyncio.get_running_loop()
        contexto_futbol = await loop.run_in_executor(None, obtener_datos_futbol_real)
        
        print("Iniciando solicitud a Grok...")
        prompt_sistema = "Sos un experto en trivias de fútbol. Responde ÚNICAMENTE con un objeto JSON estructurado que contenga un array de exactamente 40 preguntas bajo la clave 'preguntas'. Sin bloques Markdown."
        prompt_usuario = f"Basándote en estos datos reales: {json.dumps(contexto_futbol, ensure_ascii=False)} Genera un array de exactamente 40 preguntas de trivia con estructura: pregunta, opciones, correcta."
        
        completion = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="grok-beta", 
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": prompt_usuario}],
                timeout=15
            )
        )
        datos_parseados = json.loads(completion.choices.message.content)
        if "preguntas" in datos_parseados:
            BANCO_TRIVIAS = datos_parseados["preguntas"]
            print(f"¡Éxito! Se inyectaron {len(BANCO_TRIVIAS)} preguntas.")
            return
    except Exception as e:
        print(f"Fallo controlado en la generación de IA: {e}")
    
    BANCO_TRIVIAS = BANCO_RESPALDO
    print("Cargado banco de emergencias para evitar caídas de servidor.")

# CORRECCIÓN 3: Reemplazo de @app.on_event por Lifespan (Método moderno)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código que se ejecuta al iniciar la app
    asyncio.create_task(generar_banco_trivias_ai())
    yield
    # Código si quisieras hacer algo al apagar la app (vacío por ahora)

app = FastAPI(lifespan=lifespan)

# --- RUTA 1: INTERFAZ WEB ---
@app.get("/", response_class=HTMLResponse)
async def obtener_interfaz():
    try:
        ruta_html = os.path.join(os.path.dirname(__file__), "index.html")
        if os.path.exists(ruta_html):
            with open(ruta_html, "r", encoding="utf-8") as archivo:
                return HTMLResponse(content=archivo.read(), status_code=200)
    except Exception as e:
        print(f"Error al leer HTML: {e}")
    
    return HTMLResponse(content="<h1>⚽ Servidor Activo (El archivo index.html se está subiendo o procesando)</h1>", status_code=200)

# --- RUTA 2: WEBSOCKET ---
@app.websocket("/ws")
async def endpoint_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            mensaje = await websocket.receive_text()
            pass
    except WebSocketDisconnect:
        print("Un jugador se ha desconectado.")
