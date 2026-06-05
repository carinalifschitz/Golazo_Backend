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

BANCO_RESPALDO = [
    {"pregunta": "¿Quién ganó el mundial de Qatar 2022?", "opciones": ["Argentina", "Francia", "Brasil"], "correcta": "Argentina"},
    {"pregunta": "¿Quién es el máximo goleador de la Selección Argentina?", "opciones": ["Messi", "Maradona", "Batistuta"], "correcta": "Messi"},
    {"pregunta": "¿Cuál es el estadio de Boca Juniors?", "opciones": ["La Bombonera", "El Monumental", "El Cilindro"], "correcta": "La Bombonera"}
]

def obtener_datos_futbol_real():
    url_base = "https://api-sports.io"
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
                stats_list = item["statistics"]
                stats = stats_list if isinstance(stats_list, list) and len(stats_list) > 0 else stats_list
                datos_futbol["goleadores"].append({
                    "nombre": player["name"],
                    "equipo": stats.get("team", {}).get("name", "Desconocido") if isinstance(stats, dict) else "Desconocido",
                    "goles": stats.get("goals", {}).get("total", 0) if isinstance(stats, dict) else 0,
                    "nacionalidad": player["nationality"]
                })
                
        url_equipos = f"{url_base}/teams?league=128&season=2026"
        res_equipos = requests.get(url_equipos, headers=headers, timeout=5).json()
        if "response" in res_equipos:
            for item in res_equipos["response"][:12]:
                datos_futbol["estadios"].append({
                    "equipo": item["team"]["name"],
                    "estadio_nombre": item["venue"]["name"],
                    "ciudad": item["venue"]["city"],
                    "capacidad": item["venue"]["capacity"]
                })
    except Exception as e:
        print(f"Error en API-Football: {e}")
    return datos_futbol

async def generar_banco_trivias_ai():
    global BANCO_TRIVIAS
    try:
        loop = asyncio.get_running_loop()
        contexto = await loop.run_in_executor(None, obtener_datos_futbol_real)
        prompt_sistema = "Sos un experto en trivias de fútbol. Responde ÚNICAMENTE con un objeto JSON con un array de exactamente 40 preguntas bajo la clave 'preguntas'. Sin bloques Markdown."
        prompt_usuario = f"Basándote en estos datos reales: {json.dumps(contexto)} Genera un array de exactamente 40 preguntas de trivia con estructura: pregunta, opciones, correcta."
        
        completion = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="grok-beta", 
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": prompt_usuario}],
                timeout=15
            )
        )
        datos = json.loads(completion.choices.message.content)
        if "preguntas" in datos:
            BANCO_TRIVIAS = datos["preguntas"]
            print(f"¡Éxito! Inyectadas {len(BANCO_TRIVIAS)} preguntas de IA.")
            return
    except Exception as e:
        print(f"Fallo en IA: {e}")
    BANCO_TRIVIAS = BANCO_RESPALDO

@asynccontextmanager
async def lifespan(app: FastAPI):
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

# --- WEBSOCKET MODIFICADO ---
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
                # Mezclamos el banco disponible y enviamos el lote completo (máximo 40)
                pool = BANCO_TRIVIAS if BANCO_TRIVIAS else BANCO_RESPALDO
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
                    # Para el Versus Versus, mandamos 5 preguntas para que no sea eterno, o 40 si así lo preferís.
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
            del salas_activas[mi_sala]
