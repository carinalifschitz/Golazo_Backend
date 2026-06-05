import asyncio
import concurrent.futures
import json
import os
import random
import requests
import time
from openai import OpenAI
import websockets

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
                statistics = item["statistics"][0] if isinstance(item["statistics"], list) else item["statistics"]
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

# ----------------------------------------------------------------
# GENERACIÓN DE TRIVIAS (GROK)
# ----------------------------------------------------------------
async def generar_banco_trivias_ai():
    global BANCO_TRIVIAS
    print("Obteniendo estadísticas desde API-Football...")
    loop = asyncio.get_running_loop()
    contexto_futbol = await loop.run_in_executor(None, obtener_datos_futbol_real)
    print("Iniciando solicitud a Grok...")
    prompt_sistema = "Sos un experto en trivias de fútbol. Debes responder ÚNICAMENTE con un objeto JSON estructurado que contenga un array de exactamente 40 preguntas bajo la clave 'preguntas'. Sin bloques Markdown."
    prompt_usuario = f"Basándote en estos datos reales: {json.dumps(contexto_futbol, ensure_ascii=False)} Genera un array de exactamente 40 preguntas de trivia con opciones y correcta."
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
            print(f"¡Éxito! {len(BANCO_TRIVIAS)} preguntas cargadas.")
    except Exception as e:
        print(f"Fallo de IA: {e}")
        BANCO_TRIVIAS = [{"pregunta": "¿Quién ganó el mundial de Qatar 2022?", "opciones": ["Argentina", "Francia", "Brasil"], "correcta": "Argentina"}]

# ----------------------------------------------------------------
# RESPUESTA AL HEALTH CHECK (HTTP) Y MANEJO DE WEBSOCKET
# ----------------------------------------------------------------
def responder_http_render(path, request_headers):
    """Intercepta peticiones web normales (como el Health Check de Render)"""
    # Si la petición no busca explícitamente cambiar a protocolo WebSocket (Upgrade)
    if "Upgrade" not in request_headers.get("Connection", "") and "upgrade" not in request_headers.get("Upgrade", ""):
        import http
        # Devolvemos una respuesta HTTP 200 OK tradicional para mantener a Render feliz
        return http.HTTPStatus.OK, [("Content-Type", "text/plain")], b"OK - Servidor Golazo Activo"
    return None

async def manejador_websocket(websocket):
    """Maneja las conexiones exclusivas de WebSockets (wss://)"""
    try:
        async for mensaje in websocket:
            # Tu lógica de juego interna
            pass
    except websockets.exceptions.ConnectionClosed:
        pass

async def main():
    await generar_banco_trivias_ai()
    puerto = int(os.environ.get("PORT", 10000))
    
    # CORRECCIÓN DEFINITIVA: Usamos process_request para separar HTTP de WebSockets
    async with websockets.serve(
        manejador_websocket, 
        "0.0.0.0", 
        puerto,
        process_request=responder_http_render,
        ping_interval=20,
        ping_timeout=20
    ):
        print(f"Servidor híbrido (HTTP/WS) escuchando en el puerto {puerto}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
