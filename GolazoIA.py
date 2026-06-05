import asyncio
import concurrent.futures
import json
import os
import random
import requests
import time
from openai import OpenAI
import websockets
import http

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
    """
    Se conecta a la API de apifootball.com para extraer estadísticas reales.
    Utiliza la Liga Profesional Argentina (League ID: 128) y la temporada actual.
    """
    url_base = "https://api-sports.io"
    headers = {
        "x-rapidapi-host": "v3.football.api-sports.io",
        "x-rapidapi-key": FOOTBALL_API_KEY
    }
    
    datos_futbol = {
        "goleadores": [],
        "estadios": [],
        "partidos_jugados": []
    }
    
    try:
        # 1. Obtener Top Scorers (Jugadores y Goles)
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
                
        # 2. Obtener Estadios y Equipos de la liga
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

        # 3. Obtener los últimos partidos jugados
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
# GENERACIÓN DE TRIVIAS CON JSON MODE (GROK)
# ----------------------------------------------------------------
async def generar_banco_trivias_ai():
    """
    Toma todos los datos en tiempo real de partidos, goleadores y estadios,
    y genera un JSON estructurado de 40 preguntas basadas en el contexto real.
    """
    global BANCO_TRIVIAS
    print("Obteniendo estadísticas desde API-Football...")
    
    loop = asyncio.get_running_loop()
    contexto_futbol = await loop.run_in_executor(None, obtener_datos_futbol_real)
    
    print("Iniciando solicitud a Grok con los datos del fútbol real...")

    prompt_sistema = (
        "Sos un experto en trivias de fútbol. Tu única tarea es armar un juego interactivo. "
        "Debes responder ÚNICAMENTE con un objeto JSON estructurado que contenga un array "
        "de exactamente 40 preguntas bajo la clave 'preguntas'. Sin introducciones, ni bloques Markdown."
    )

    prompt_usuario = f"""
    Basándote en los siguientes datos reales proporcionados por la API de fútbol:
    {json.dumps(contexto_futbol, ensure_ascii=False)}
    
    Genera un array de exactamente 40 preguntas de trivia de fútbol variadas:
    - Diseña preguntas usando los datos de 'partidos_jugados' (ej: quién ganó cierto partido, cuántos goles hubo, etc).
    - Diseña preguntas usando los datos de 'goleadores' (goles de jugadores actuales, sus equipos o nacionalidad).
    - Diseña preguntas usando los datos de 'estadios' (capacidad, ciudad o a qué equipo le pertenece).
    
    Cada pregunta debe seguir esta estructura JSON exacta:
    {{"pregunta": "texto", "opciones": ["opcion1", "opcion2", "opcion3"], "correcta": "opcion_exacta"}}
    
    Asegúrate de que la respuesta 'correcta' sea idéntica a una de las opciones del array.
    """

    try:
        completion = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="grok-beta", 
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_usuario}
                ]
            )
        )

        contenido_crudo = completion.choices.message.content
        datos_parseados = json.loads(contenido_crudo)
        
        if "preguntas" in datos_parseados and isinstance(datos_parseados["preguntas"], list):
            BANCO_TRIVIAS = datos_parseados["preguntas"]
            print(f"¡Éxito! Se inyectaron {len(BANCO_TRIVIAS)} preguntas reales en el servidor.")
        else:
            print("Error: El formato de la IA no contiene el nodo 'preguntas'.")

    except Exception as e:
        print(f"Fallo crítico en la generación de IA: {e}")
        BANCO_TRIVIAS = [
            {"pregunta": "¿Qué selección ganó el mundial de Qatar 2022?", "opciones": ["Argentina", "Francia", "Brasil"], "correcta": "Argentina"},
            {"pregunta": "¿Quién es el máximo goleador de la Selección Argentina?", "opciones": ["Messi", "Maradona", "Batistuta"], "correcta": "Messi"}
        ]

# ----------------------------------------------------------------
# COMPATIBILIDAD RENDER (HTTP HEALTH CHECK & BYPASS CORS)
# ----------------------------------------------------------------
def responder_http_render(path, request_headers):
    """
    Permite el tráfico de orígenes cruzados (CORS) y responde con un 200 OK 
    a las solicitudes HTTP comunes que realiza Render para el monitoreo.
    """
    if "upgrade" not in request_headers.get("Connection", "").lower() and "upgrade" not in request_headers.get("Upgrade", "").lower():
        # Cabeceras abiertas para anular el bloqueo CORS del navegador
        headers = [
            ("Content-Type", "text/plain"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "*")
        ]
        return http.HTTPStatus.OK, headers, b"OK - Servidor Golazo Activo"
    return None

# ----------------------------------------------------------------
# LOGICA DEL WEBSOCKET (SALAS DE JUEGO)
# ----------------------------------------------------------------
async def manejador_websocket(websocket):
    """
    Maneja las interacciones exclusivas del protocolo de WebSocket.
    Aquí podés restablecer tu lógica de mensajes, salas y jugadores.
    """
    try:
        async for mensaje in websocket:
            # Tu bloque de procesamiento de lógica del juego va aquí...
            pass
    except websockets.exceptions.ConnectionClosed:
        pass

async def main():
    # 1. Ejecutar descarga e inyección de trivias con Grok
    await generar_banco_trivias_ai()

    # 2. Configurar enlace de puerto dinámico obligatorio para Render
    puerto = int(os.environ.get("PORT", 10000))
    
    async with websockets.serve(
        manejador_websocket, 
        "0.0.0.0", 
        puerto,
        process_request=responder_http_render,
        ping_interval=20,  # Previene cierres por inactividad del balanceador
        ping_timeout=20
    ):
        print(f"Servidor WebSocket e HTTP con CORS escuchando en el puerto {puerto}")
        await asyncio.Future() 

if __name__ == "__main__":
    asyncio.run(main())
