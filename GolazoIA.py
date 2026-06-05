import asyncio
import concurrent.futures
import json
import os
import requests
import time
from openai import OpenAI
import websockets

# --- CONFIGURACIÓN DE CREDENCIALES ---
GROK_API_KEY = os.environ.get("GROK_API_KEY", "TU_API_KEY_DE_GROK")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "TU_API_KEY_DE_API_FOOTBALL")

client = OpenAI(
    api_key=GROK_API_KEY, 
    base_url="https://xai.tech"
)

# --- VARIABLES DE CONTROL Y BANCO DE TRIVIAS ---
BANCO_TRIVIAS = []
INDICE_INDIVIDUAL = {}

jugadores_esperando = []
salas_activas = {}
RANKING_GLOBAL = {}

TRIVIA_RESPALDO = {
    "pregunta": "¿En qué minuto anotó Gonzalo Montiel el penal definitivo para Argentina en la final de Qatar 2022?", 
    "opciones": ["En la tanda de penales", "Minuto 90", "Minuto 120"], 
    "correcta": "En la tanda de penales"
}

# ----------------------------------------------------------------
# LÓGICA DE DATOS & INTELIGENCIA ARTIFICIAL (HILO SEPARADO)
# ----------------------------------------------------------------

def consultar_api_futbol_masivo():
    """Consulta los últimos 40 partidos con todos sus eventos detallados."""
    url = "https://api-sports.io"
    querystring = {"league": "128", "season": "2026", "status": "FT", "last": "40"}
    headers = {'x-apisports-key': FOOTBALL_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()
        if data and data.get('response') and len(data['response']) > 0:
            return data['response']
    except Exception as e:
        print(f"[ERROR API FÚTBOL]: {e}")
    return None

def generar_trivia_de_partido(partido_raw):
    """Envía el objeto del partido a Grok para extraer la trivia."""
    partido_string = json.dumps(partido_raw)
    
    prompt = f"""
    Basándote estrictamente en los datos estructurados de este partido de fútbol en formato JSON:
    {partido_string}
    
    Generá UNA pregunta de trivia que sea sumamente variada y específica. 
    NO preguntes simplemente quién ganó el partido. Rotá de forma inteligente entre estas temáticas:
    1. ¿Qué jugador anotó un gol específico en este partido?
    2. ¿En qué estadio o ciudad se disputó este encuentro?
    3. ¿Cuántos goles en total se marcaron o cuál fue el resultado exacto del primer tiempo?
    4. ¿Hubo alguna tarjeta roja, penal o evento crítico en un minuto específico?
    
    La pregunta debe tener exactamente 3 opciones de respuesta corta, clara y concisa.
    
    REQUERIMIENTO OBLIGATORIO DE SALIDA (JSON Puro):
    {{
        "pregunta": "texto de la pregunta específica", 
        "opciones": ["op1", "op2", "op3"], 
        "correcta": "texto_exacto_de_la_opcion_correcta"
    }}
    """
    try:
        completion = client.chat.completions.create(
            model="grok-2",
            messages=[
                {"role": "system", "content": "Sos un experto estadígrafo de fútbol que solo responde en formato JSON estricto."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.65
        )
        return json.loads(completion.choices[0].message.content.strip())
    except Exception as e:
        print(f"[ERROR GENERANDO PREGUNTA DETALLADA]: {e}")
        return None

def precargar_banco_trivias_sincrono():
    """Ejecuta la descarga y procesamiento pesado en un hilo secundario."""
    global BANCO_TRIVIAS
    print("[SISTEMA]: Iniciando descarga de 40 partidos detallados en segundo plano...")
    partidos = consultar_api_futbol_masivo()
    
    if partidos:
        for i, partido in enumerate(partidos):
            print(f"[SISTEMA]: Procesando estadísticas del partido {i+1}/40 con Grok...")
            trivia = generar_trivia_de_partido(partido)
            if trivia:
                BANCO_TRIVIAS.append(trivia)
            # Pausa síncrona para no saturar las APIs
            time.sleep(0.5)
            
    print(f"[SISTEMA]: Banco cargado con éxito. Total preguntas listas: {len(BANCO_TRIVIAS)}")

# ----------------------------------------------------------------
# LÓGICA DE RED (WEBSOCKETS COMPETITIVO MULTIJUGADOR)
# ----------------------------------------------------------------

async def manejar_cliente(websocket):
    global jugadores_esperando, salas_activas, RANKING_GLOBAL, BANCO_TRIVIAS, INDICE_INDIVIDUAL
    
    nombre_jugador = f"User_{id(websocket) % 1000}"
    if nombre_jugador not in RANKING_GLOBAL:
        RANKING_GLOBAL[nombre_jugador] = 0
    if nombre_jugador not in INDICE_INDIVIDUAL:
        INDICE_INDIVIDUAL[nombre_jugador] = 0

    print(f"[RED]: {nombre_jugador} se ha conectado.")
    
    try:
        async for mensaje in websocket:
            datos = json.loads(mensaje)
            accion = datos.get("accion")
            
            trivias_disponibles = BANCO_TRIVIAS if len(BANCO_TRIVIAS) > 0 else [TRIVIA_RESPALDO]
            
            # --- MODO INDIVIDUAL ---
            if accion == "jugar_individual":
                idx = INDICE_INDIVIDUAL[nombre_jugador]
                if idx >= len(trivias_disponibles):
                    idx = 0
                    INDICE_INDIVIDUAL[nombre_jugador] = 0
                
                trivia_actual = trivias_disponibles[idx]
                
                await websocket.send(json.dumps({
                    "tipo": "trivia", 
                    "id_sala": "",
                    "datos": trivia_actual
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
                    
                    import random
                    trivia_sala = random.choice(trivias_disponibles)
                    
                    salas_activas[id_sala] = {
                        "jugadores": [j1, j2],
                        "tiempo_inicio": time.time(),
                        "trivia": trivia_sala,
                        "respuestas_recibidas": {}
                    }
                    
                    payload_inicio = json.dumps({
                        "tipo": "inicio_multijugador",
                        "id_sala": id_sala,
                        "datos": trivia_sala
                    })
                    
                    await j1.send(payload_inicio)
                    await j2.send(payload_inicio)
                    
            # --- PROCESAMIENTO DE RESPUESTAS ---
            elif accion == "responder":
                id_sala = datos.get("id_sala")
                eleccion = datos.get("eleccion")
                
                # --- RESPUESTA EN MODO INDIVIDUAL AUTOMÁTICO ---
                if not id_sala or id_sala == "":
                    idx = INDICE_INDIVIDUAL[nombre_jugador]
                    trivia_obj = trivias_disponibles[idx]
                    
                    es_correcto = (eleccion == trivia_obj.get("correcta"))
                    if es_correcto:
                        RANKING_GLOBAL[nombre_jugador] += 100
                    
                    # Avanzamos el índice para calcular la que sigue
                    INDICE_INDIVIDUAL[nombre_jugador] += 1
                    nuevo_idx = INDICE_INDIVIDUAL[nombre_jugador]
                    
                    # Control de ciclo: si llegó al tope (40), resetea a la primera
                    if nuevo_idx >= len(trivias_disponibles):
                        nuevo_idx = 0
                        INDICE_INDIVIDUAL[nombre_jugador] = 0
                    
                    siguiente_trivia = trivias_disponibles[nuevo_idx]
                    
                    # Enviamos el veredicto actual Y la próxima pregunta adjunta en el mismo payload
                    await websocket.send(json.dumps({
                        "tipo": "resultado", 
                        "correcto": es_correcto,
                        "ranking_global": RANKING_GLOBAL,
                        "siguiente_pregunta": siguiente_trivia
                    }))
                    continue
                
                # --- RESPUESTA EN MODO MULTIJUGADOR ---
                if id_sala in salas_activas:
                    sala = salas_activas[id_sala]
                    tiempo_respuesta = time.time() - sala["tiempo_inicio"]
                    es_correcto = (eleccion == sala["trivia"].get("correcta"))
                    
                    sala["respuestas_recibidas"][websocket] = {
                        "nombre": nombre_jugador,
                        "correcto": es_correcto,
                        "tiempo": tiempo_respuesta
                    }
                    
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
                        
                        for jugador_ws in sala["jugadores"]:
                            try:
                                await jugador_ws.send(payload_fin)
                            except Exception:
                                pass
                                
                        del salas_activas[id_sala]

    except websockets.exceptions.ConnectionClosed:
        print(f"[RED]: {nombre_jugador} desconectado.")
    finally:
        if websocket in jugadores_esperando:
            jugadores_esperando.remove(websocket)

# ----------------------------------------------------------------
# FUNCIÓN DE INICIO PRINCIPAL
# ----------------------------------------------------------------

async def main():
    # Lanzamos la precarga pesada en un hilo paralelo para no congelar los websockets
    loop = asyncio.get_running_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    loop.run_in_executor(executor, precargar_banco_trivias_sincrono)
    
    # Configuración de puerto para Render
    puerto = int(os.environ.get("PORT", 8765))
    print(f"[SISTEMA]: Iniciando servidor WebSocket en 0.0.0.0:{puerto}")
    
    # Desactivamos restricciones de origen (origins=None) para permitir conexiones de prueba externas
    async with websockets.serve(manejar_cliente, "0.0.0.0", puerto, origins=None):
        await asyncio.Future()  # Mantiene el servidor escuchando para siempre

if __name__ == "__main__":
    asyncio.run(main())
