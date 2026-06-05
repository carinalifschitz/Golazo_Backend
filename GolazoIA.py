import asyncio
import json
import os
import requests
import random
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

# --- VARIABLES DE CONTROL GLOBAL ---
BANCO_TRIVIAS = []
jugadores_esperando = []  
salas_activas = {}       

# Banco de emergencias garantizado: Si todo falla, este lote mantiene tu app viva.
BANCO_RESPALDO = [
    {"pregunta": "¿Quién ganó el mundial de Qatar 2022?", "opciones": ["Argentina", "Francia", "Brasil"], "correcta": "Argentina"},
    {"pregunta": "¿Quién es el máximo goleador de la Selección Argentina?", "opciones": ["Messi", "Maradona", "Batistuta"], "correcta": "Messi"},
    {"pregunta": "¿Cuál es el estadio de Boca Juniors?", "opciones": ["La Bombonera", "El Monumental", "El Cilindro"], "correcta": "La Bombonera"},
    {"pregunta": "¿Qué equipo tiene más Copas Libertadores?", "opciones": ["Independiente", "Boca", "River"], "correcta": "Independiente"}
]

def obtener_datos_futbol_real():
    url_base = "https://v3.football.api-sports.io"
    # CORRECCIÓN CLAVE: Se añaden ambas variantes de Headers para máxima compatibilidad con API-Football
    headers = {
        "x-rapidapi-host": "v3.football.api-sports.io",
        "x-rapidapi-key": FOOTBALL_API_KEY,
        "x-apisports-key": FOOTBALL_API_KEY
    }
    datos_futbol = {"goleadores": [], "estadios": [], "partidos_jugados": []}
    
    # Usamos una temporada con datos garantizados (2024 o 2025 según liga) para evitar respuestas vacías
    temporada = "2024" 
    liga_id = "128" # Liga Profesional Argentina

    # Sub-bloque 1: Goleadores
    try:
        url_goleadores = f"{url_base}/players/topscorers?league={liga_id}&season={temporada}"
        res_goleadores = requests.get(url_goleadores, headers=headers, timeout=5).json()
        if "response" in res_goleadores and isinstance(res_goleadores["response"], list):
            for item in res_goleadores["response"][:12]:
                player = item.get("player", {})
                stats_list = item.get("statistics", [])
                stats = stats_list[0] if isinstance(stats_list, list) and len(stats_list) > 0 else {}
                
                datos_futbol["goleadores"].append({
                    "nombre": player.get("name", "Desconocido"),
                    "equipo": stats.get("team", {}).get("name", "Desconocido"),
                    "goles": stats.get("goals", {}).get("total", 0),
                    "nacionalidad": player.get("nationality", "Desconocida")
                })
    except Exception as e:
        print(f"Aviso: Falló la extracción de goleadores ({e})")

    # Sub-bloque 2: Equipos y Estadios
    try:
        url_equipos = f"{url_base}/teams?league={liga_id}&season={temporada}"
        res_equipos = requests.get(url_equipos, headers=headers, timeout=5).json()
        if "response" in res_equipos and isinstance(res_equipos["response"], list):
            for item in res_equipos["response"][:12]:
                team = item.get("team", {})
                venue = item.get("venue", {})
                if team.get("name") and venue.get("name"):
                    datos_futbol["estadios"].append({
                        "equipo": team.get("name"),
                        "estadio_nombre": venue.get("name"),
                        "ciudad": venue.get("city", "Desconocida"),
                        "capacidad": venue.get("capacity", 0)
                    })
    except Exception as e:
        print(f"Aviso: Falló la extracción de estadios ({e})")

    return datos_futbol

async def generar_banco_trivias_ai():
    global BANCO_TRIVIAS
    try:
        print("Iniciando recolección de estadísticas...")
        loop = asyncio.get_running_loop()
        contexto = await loop.run_in_executor(None, obtener_datos_futbol_real)
        
        # Validar si logramos recolectar datos reales mínimos
        if not contexto["goleadores"] and not contexto["estadios"]:
            print("API-Football no retornó datos válidos. Saltando directo al banco de respaldo.")
            BANCO_TRIVIAS = BANCO_RESPALDO
            return

        print("Enviando contexto a Grok...")
        prompt_sistema = "Sos un experto en trivias de fútbol. Responde ÚNICAMENTE con un objeto JSON con un array de exactamente 40 preguntas bajo la clave 'preguntas'. Sin bloques Markdown ni explicaciones."
        prompt_usuario = f"Basándote en estos datos reales: {json.dumps(contexto, ensure_ascii=False)} Genera un array de exactamente 40 preguntas de trivia con la estructura exacta: pregunta, opciones, correcta."
        
        completion = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="grok-beta", 
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": prompt_usuario}],
                timeout=20
            )
        )
        
        datos = json.loads(completion.choices.message.content)
        if "preguntas" in datos and len(datos["preguntas"]) > 0:
            # Forzar mezcla aleatoria del banco recibido
            BANCO_TRIVIAS = datos["preguntas"]
            print(f"¡Éxito total! Inyectadas {len(BANCO_TRIVIAS)} preguntas dinámicas desde la IA.")
            return
            
    except Exception as e:
        print(f"Error crítico controlado en el generador de IA: {e}")
    
    # Resguardo de seguridad inquebrantable
    print("Inyectando banco de respaldo preventivo por fallas generales.")
    BANCO_TRIVIAS = BANCO_RESPALDO

@asynccontextmanager
async def lifespan(app: FastAPI):
    # La tarea corre en background absoluto para que Uvicorn asigne el puerto HTTP de inmediato en Render
    asyncio.create_task(generar_banco_trivias_ai())
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def obtener_interfaz():
    ruta_html = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(ruta_html):
        with open(ruta_html, "r", encoding="utf-8") as archivo:
            return HTMLResponse(content=archivo.read(), status_code=200)
    return HTMLResponse(content="<h1>⚽ Servidor Activo (Subiendo index.html...)</h1>", status_code=200)

# --- SISTEMA WEBSOCKET UNIFICADO ---
@app.websocket("/ws")
async def endpoint_websocket(websocket: WebSocket):
    await websocket.accept()
    mi_sala = None
    try:
        while True:
            data = await websocket.receive_text()
            mensaje = json.loads(data)
            accion = mensaje.get("accion")

            if accion == "solicitar_individual":
                pool = BANCO_TRIVIAS if BANCO_TRIVIAS else BANCO_RESPALDO
                # Selecciona aleatoriamente hasta 40 preguntas del set disponible
                preguntas_mezcladas = random.sample(pool, min(40, len(pool)))
                await websocket.send_text(json.dumps({
                    "tipo": "banco_individual", 
                    "preguntas": preguntas_mezcladas
                }))

            elif accion == "buscar_match":
                if websocket not in jugadores_esperando:
                    jugadores_esperando.append(websocket)
                
                if len(jugadores_esperando) >= 2:
                    p1 = jugadores_esperando.pop(0)
                    p2 = jugadores_esperando.pop(0)
                    mi_sala = f"sala_{random.randint(1000, 9999)}"
                    
                    pool = BANCO_TRIVIAS if BANCO_TRIVIAS else BANCO_RESPALDO
                    preguntas_partida = random.sample(pool, min(40, len(pool)))
                    
                    salas_activas[mi_sala] = {
                        "jugadores": [p1, p2],
                        "preguntas": preguntas_partida
                    }
                    
                    payload = json.dumps({
                        "tipo": "match_encontrado",
                        "salaId": mi_sala,
                        "preguntas": preguntas_partida
                    })
                    await p1.send_text(payload)
                    await p2.send_text(payload)

            elif accion == "cancelar_busqueda":
                if websocket in jugadores_esperando:
                    jugadores_esperando.remove(websocket)

            elif accion == "enviar_actualizacion":
                sala_id = mensaje.get("salaId")
                if sala_id in salas_activas:
                    for jugador in salas_activas[sala_id]["jugadores"]:
                        if jugador != websocket:
                            await jugador.send_text(json.dumps({
                                "tipo": "actualizacion_rival",
                                "puntos_rival": mensaje.get("puntos"),
                                "progreso_rival": mensaje.get("progreso")
                            }))

    except WebSocketDisconnect:
        if websocket in jugadores_esperando:
            jugadores_esperando.remove(websocket)
        if mi_sala and mi_sala in salas_activas:
            for jugador in salas_activas[mi_sala]["jugadores"]:
                try:
                    await jugador.send_text(json.dumps({"tipo": "rival_desconectado"}))
                except:
                    pass
            if mi_sala in salas_activas:
                del salas_activas[mi_sala]
