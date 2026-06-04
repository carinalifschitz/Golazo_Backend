import asyncio
import json
import os  # <- Módulo integrado para leer variables de entorno del servidor
import requests
import time
from openai import OpenAI
import websockets

# --- CONFIGURACIÓN DE CREDENCIALES ---
GROK_API_KEY = "TU_API_KEY_DE_GROK"
FOOTBALL_API_KEY = "TU_API_KEY_DE_API_FOOTBALL"

# Inicialización oficial de Grok (xAI) usando compatibilidad OpenAI
client = OpenAI(
    api_key=GROK_API_KEY, 
    base_url="https://api.xai.tech/v1"
)

# --- VARIABLES DE CONTROL (CACHÉ, SALAS Y RANKING) ---
ULTIMO_PARTIDO_ID = None
TRIVIA_ACTUAL_JSON = '{"pregunta": "Cargando trivia...", "opciones": ["-", "-", "-"], "correcta": ""}'

jugadores_esperando = []
salas_activas = {}
RANKING_GLOBAL = {}  # Estructura en memoria: {"NombreJugador": PuntajeAcumulado}

# ----------------------------------------------------------------
# LÓGICA DE DATOS & INTELIGENCIA ARTIFICIAL (CACHÉ)
# ----------------------------------------------------------------

def consultar_api_futbol():
    """Consulta el último partido finalizado (FT) en la liga configurada."""
    url = "https://v3.football.api-sports.io/fixtures"
    querystring = {"league": "128", "season": "2026", "status": "FT", "last": "1"}
    headers = {
        'x-rapidapi-host': "v3.football.api-sports.io",
        'x-rapidapi-key': FOOTBALL_API_KEY
    }
    try:
        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()
        if data and data.get('response'):
            return data['response'][0]
    except Exception as e:
        print(f"[ERROR API FÚTBOL]: {e}")
    return None

def generar_nueva_trivia(partido_raw):
    """Invoca a Grok nativamente para estructurar el JSON."""
    local = partido_raw['teams']['home']['name']
    visitante = partido_raw['teams']['away']['name']
    goles_l = partido_raw['goals']['home']
    goles_v = partido_raw['goals']['away']
    
    prompt = f"""
    Generá una pregunta de trivia de fútbol basada estrictamente en este partido reciente:
    {local} ({goles_l}) vs {visitante} ({goles_v}).
    La pregunta debe tener exactamente 3 opciones de respuesta corta y concisa.
    
    Estructura requerida:
    {{
        "pregunta": "texto de la pregunta", 
        "opciones": ["op1", "op2", "op3"], 
        "correcta": "texto_exacto_de_la_opcion_correcta"
    }}
    """
    try:
        # Configuración optimizada nativa para el modelo de Grok
        completion = client.chat.completions.create(
            model="grok-2",
            messages=[
                {"role": "system", "content": "Sos un backend automatizado que solo responde JSON estricto."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}, # Fuerza a Grok a responder JSON válido
            temperature=0.2
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR GROK]: {e}")
        return None

async def bucle_verificacion_partidos():
    """Revisa la API de fútbol cada 5 minutos. Si el partido cambia, actualiza la trivia."""
    global ULTIMO_PARTIDO_ID, TRIVIA_ACTUAL_JSON
    while True:
        print("[SISTEMA]: Verificando actualización de partidos...")
        partido = consultar_api_futbol()
        if partido:
            id_partido_api = partido['fixture']['id']
            if id_partido_api != ULTIMO_PARTIDO_ID:
                print(f"[NUEVO PARTIDO]: ID {id_partido_api} detectado. Actualizando caché con Grok...")
                nuevo_json = generar_nueva_trivia(partido)
                if nuevo_json:
                    TRIVIA_ACTUAL_JSON = nuevo_json
                    ULTIMO_PARTIDO_ID = id_partido_api
                    print("[SISTEMA]: Caché de Trivia actualizado con éxito.")
            else:
                print("[SISTEMA]: El último partido no ha variado. Manteniendo caché.")
        await asyncio.sleep(300)

# ----------------------------------------------------------------
# LÓGICA DE RED (WEBSOCKETS COMPETITIVO MULTIJUGADOR)
# ----------------------------------------------------------------

async def manejar_cliente(websocket):
    global jugadores_esperando, salas_activas, RANKING_GLOBAL
    
    nombre_jugador = f"User_{id(websocket) % 1000}"
    if nombre_jugador not in RANKING_GLOBAL:
        RANKING_GLOBAL[nombre_jugador] = 0

    print(f"[RED]: {nombre_jugador} se ha conectado.")
    
    try:
        async for mensaje in websocket:
            datos = json.loads(mensaje)
            accion = datos.get("accion")
            
            # --- MODO INDIVIDUAL ---
            if accion == "jugar_individual":
                await websocket.send(json.dumps({
                    "tipo": "trivia", 
                    "id_sala": "",
                    "datos": json.loads(TRIVIA_ACTUAL_JSON)
                }))
                
            # --- MATCHMAKING MULTIJUGADOR ---
            elif accion == "buscar_partida_multijugador":
                if websocket not in jugadores_esperando:
                    jugadores_esperando.append(websocket)
                    await websocket.send(json.dumps({"tipo": "status", "mensaje": "Buscando rival..."}))
                
                if len(jugadores_esperando) >= 2:
                    j1 = jugadores_esperando.pop(0)
                    j2 = jugadores_esperando.pop(0)
                    
                    id_sala = f"sala_{id(j1)}"
                    salas_activas[id_sala] = {
                        "jugadores": [j1, j2],
                        "tiempo_inicio": time.time(),
                        "respuestas_recibidas": {}
                    }
                    
                    payload_inicio = json.dumps({
                        "tipo": "inicio_multijugador",
                        "id_sala": id_sala,
                        "datos": json.loads(TRIVIA_ACTUAL_JSON)
                    })
                    
                    await j1.send(payload_inicio)
                    await j2.send(payload_inicio)
                    print(f"[SALA]: {id_sala} iniciada entre dos rivales.")
                    
            # --- PROCESAMIENTO DE RESPUESTAS & LÓGICA DE PUNTOS ---
            elif accion == "responder":
                id_sala = datos.get("id_sala")
                eleccion = datos.get("eleccion")
                trivia_obj = json.loads(TRIVIA_ACTUAL_JSON)
                
                if not id_sala or id_sala == "":
                    es_correcto = (eleccion == trivia_obj.get("correcta"))
                    if es_correcto:
                        RANKING_GLOBAL[nombre_jugador] += 100
                    
                    await websocket.send(json.dumps({
                        "tipo": "resultado", 
                        "correcto": es_correcto,
                        "ranking_global": RANKING_GLOBAL
                    }))
                    continue
                
                if id_sala in salas_activas:
                    sala = salas_activas[id_sala]
                    tiempo_respuesta = time.time() - sala["tiempo_inicio"]
                    es_correcto = (eleccion == trivia_obj.get("correcta"))
                    
                    sala["respuestas_recibidas"][websocket] = {
                        "nombre": nombre_jugador,
                        "correcto": es_correcto,
                        "tiempo": tiempo_respuesta
                    }
                    
                    # Evaluación cuando ambos terminan de responder en la sala
                    if len(sala["respuestas_recibidas"]) == 2:
                        ganador_sala = "Empate / Nadie acertó"
                        mejor_tiempo = 9999.0
                        ws_ganador = None
                        
                        for ws_cliente, res in sala["respuestas_recibidas"].items():
                            if res["correcto"] and res["tiempo"] < mejor_tiempo:
                                mejor_tiempo = res["tiempo"]
                                ganador_sala = res["nombre"]
                                ws_ganador = ws_cliente
                        
                        if ws_ganador:
                            RANKING_GLOBAL[ganador_sala] += 100
                        
                        payload_fin = json.dumps({
                            "tipo": "fin_partida",
                            "ganador": ganador_sala,
                            "ranking_global": RANKING_GLOBAL
                        })
                        
                        # Notificar fin de partida a todos los contrincantes de la sala
                        for jugador_ws in sala["jugadores"]:
                            try:
                                await jugador_ws.send(payload_fin)
                            except Exception:
                                pass
                                
                        del salas_activas[id_sala]
                        print(f"[SALA]: {id_sala} cerrada con éxito. Ganador: {ganador_sala}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[RED]: {nombre_jugador} desconectado.")
    finally:
        if websocket in jugadores_esperando:
            jugadores_esperando.remove(websocket)

async def main():
    # Inicializa el demonio de sincronización de partidos en segundo plano
    asyncio.create_task(bucle_verificacion_partidos())
    
    # El servidor lee dinámicamente el puerto asignado por Render (o usa 8765 localmente)
    puerto = int(os.environ.get("PORT", 8765))
    print(f"[SISTEMA]: Iniciando servidor WebSocket en 0.0.0.0:{puerto}")
    
    async with websockets.serve(manejar_cliente, "0.0.0.0", puerto):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
