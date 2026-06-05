import asyncio
import json
import os
import requests
import random
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# --- CONFIGURACIÓN DE CREDENCIALES DESDE RENDER ---
GROK_API_KEY = os.environ.get("GROK_API_KEY")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY")

# --- BANCO DE RESPALDO INTEGRADO (Solo actúa si no hay internet o saldo) ---
BANCO_RESPALDO = [
    {"pregunta": "¿Quién ganó el mundial de Qatar 2022?", "opciones": ["Argentina", "Francia", "Brasil"], "correcta": "Argentina"},
    {"pregunta": "¿Quién es el máximo goleador histórico de la Selección Argentina?", "opciones": ["Lionel Messi", "Gabriel Batistuta", "Diego Maradona"], "correcta": "Lionel Messi"},
    {"pregunta": "¿En qué club europeo debutó profesionalmente Sergio 'Kun' Agüero?", "opciones": ["Atlético de Madrid", "Manchester City", "Barcelona"], "correcta": "Atlético de Madrid"},
    {"pregunta": "¿Quién fue el director técnico de la Selección Argentina en el Mundial de Sudáfrica 2010?", "opciones": ["Diego Maradona", "Alejandro Sabella", "Alfio Basile"], "correcta": "Diego Maradona"},
    {"pregunta": "¿Qué país organizó y ganó el Mundial de fútbol de 1998?", "opciones": ["Francia", "Brasil", "Italia"], "correcta": "Francia"},
    {"pregunta": "¿Cuál es el estadio de fútbol con mayor capacidad de espectadores en Sudamérica?", "opciones": ["Estadio Mâs Monumental", "Estadio Maracaná", "Estadio Centenario"], "correcta": "Estadio Mâs Monumental"},
    {"pregunta": "¿Quién anotó el famoso gol conocido como 'La mano de Dios' en 1986?", "opciones": ["Diego Maradona", "Jorge Burruchaga", "Gary Lineker"], "correcta": "Diego Maradona"},
    {"pregunta": "¿Qué club de la Liga Argentina es conocido popularmente como 'El Taladro'?", "opciones": ["Banfield", "Lanús", "Temperley"], "correcta": "Banfield"},
    {"pregunta": "¿Quién ganó el Balón de Oro en el año 2023?", "opciones": ["Lionel Messi", "Erling Haaland", "Kylian Mbappé"], "correcta": "Lionel Messi"},
    {"pregunta": "¿Cuál de estos equipos NO descendió nunca de la Primera División de Argentina?", "opciones": ["Boca Juniors", "River Plate", "Independiente"], "correcta": "Boca Juniors"}
]

def obtener_datos_futbol_real():
    url_base = "https://api-sports.io"
    headers = {
        "x-rapidapi-host": "v3.football.api-sports.io",
        "x-rapidapi-key": FOOTBALL_API_KEY,
        "x-apisports-key": FOOTBALL_API_KEY
    }
    datos_futbol = {"goleadores": [], "estadios": []}
    try:
        # Liga 128 (Argentina) - Temporada 2024 (Datos reales consolidados estables)
        url_goleadores = f"{url_base}/players/topscorers?league=128&season=2024"
        res_goleadores = requests.get(url_goleadores, headers=headers, timeout=5).json()
        if "response" in res_goleadores and isinstance(res_goleadores["response"], list):
            for item in res_goleadores["response"][:8]:
                player = item.get("player", {})
                stats_list = item.get("statistics", [])
                stats = stats_list[0] if isinstance(stats_list, list) and len(stats_list) > 0 else {}
                datos_futbol["goleadores"].append({
                    "nombre": player.get("name", "Desconocido"),
                    "equipo": stats.get("team", {}).get("name", "Desconocido")
                })
    except Exception as e:
        print(f"[API FÚTBOL] Error al recolectar datos: {e}")
    return datos_futbol

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def obtener_interfaz():
    ruta_html = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(ruta_html):
        with open(ruta_html, "r", encoding="utf-8") as archivo:
            return HTMLResponse(content=archivo.read(), status_code=200)
    return HTMLResponse(content="<h1>⚽ Servidor Golazo IA Activo</h1>", status_code=200)

@app.get("/api/trivias")
async def obtener_trivias_http():
    if not GROK_API_KEY:
        print("[GROK] Error: La variable GROK_API_KEY está vacía en Render.")
        copia_respaldo = list(BANCO_RESPALDO)
        random.shuffle(copia_respaldo)
        return {"preguntas": copia_respaldo}

    # 1. Obtener contexto del fútbol real
    loop = asyncio.get_running_loop()
    contexto = await loop.run_in_executor(None, obtener_datos_futbol_real)
    
    # Forzar un contexto simulado si la API de fútbol no devolvió nada (para obligar a Grok a actuar)
    if not contexto.get("goleadores"):
        contexto = {
            "goleadores": [
                {"nombre": "Miguel Borja", "equipo": "River Plate"},
                {"nombre": "Edinson Cavani", "equipo": "Boca Juniors"},
                {"nombre": "Adrian Martinez", "equipo": "Racing Club"},
                {"nombre": "Walter Bou", "equipo": "Lanús"}
            ]
        }

    # 2. Conectar con la API oficial de xAI usando un modelo vigente (grok-2)
    try:
        url_grok = "https://api.x.ai/v1/chat/completions"
        headers_grok = {
            "Authorization": f"Bearer {GROK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt_sistema = (
            "Eres un experto en fútbol. Debes responder ÚNICAMENTE con un objeto JSON válido. "
            "El formato del JSON debe contener una clave llamada 'preguntas' que almacene un array con exactamente 40 objetos. "
            "Cada objeto debe tener la estructura exacta: "
            "{'pregunta': 'string', 'opciones': ['string1', 'string2', 'string3'], 'correcta': 'string'}. "
            "No incluyas bloques de código ni texto fuera del objeto JSON."
        )
        
        prompt_usuario = (
            f"Basándote en estos datos de jugadores: {json.dumps(contexto, ensure_ascii=False)}. "
            "Genera exactamente 40 preguntas de trivia de fútbol. Al menos 15 preguntas deben mencionar "
            "directamente a los jugadores o equipos incluidos en los datos provistos. Las demás preguntas "
            "deben ser de cultura general del fútbol argentino e internacional. Recuerda que el campo 'correcta' "
            "debe coincidir textualmente con una de las opciones del array."
        )

        payload = {
            "model": "grok-2",  # CORRECCIÓN CLAVE: Usamos el modelo estable vigente, no grok-beta
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            "temperature": 0.7
        }

        print("[GROK] Enviando solicitud a la API de xAI...")
        res = requests.post(url_grok, json=payload, headers=headers_grok, timeout=15)
        
        if res.status_code == 200:
            datos_api = res.json()
            contenido_texto = datos_api["choices"][0]["message"]["content"]
            datos_parseados = json.loads(contenido_texto)
            
            if "preguntas" in datos_parseados and len(datos_parseados["preguntas"]) > 0:
                print(f"[GROK] ¡Éxito total! Generadas {len(datos_parseados['preguntas'])} preguntas de actualidad.")
                preguntas_ia = datos_parseados["preguntas"]
                random.shuffle(preguntas_ia)
                return {"preguntas": preguntas_ia}
        else:
            print(f"[GROK] Error de API. Código de estado: {res.status_code}. Respuesta: {res.text}")
            
    except Exception as e:
        print(f"[GROK] Excepción crítica al procesar la solicitud: {e}")
    
    # 3. Retorno de emergencia mezclado si las llamadas fallan
    print("[SERVER] Retornando el mazo de respaldo mezclado de forma aleatoria.")
    copia_respaldo = list(BANCO_RESPALDO)
    random.shuffle(copia_respaldo)
    return {"preguntas": copia_respaldo}
