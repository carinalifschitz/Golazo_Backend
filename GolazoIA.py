import asyncio
import json
import os
import requests
import random
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from openai import OpenAI

# --- CONFIGURACIÓN DE CREDENCIALES ---
GROK_API_KEY = os.environ.get("GROK_API_KEY", "TU_API_KEY_DE_GROK")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "TU_API_KEY_DE_API_FOOTBALL")

client = OpenAI(
    api_key=GROK_API_KEY, 
    base_url="https://x.ai"
)

# --- BANCO DE EMERGENCIAS ---
BANCO_RESPALDO = [
    {"pregunta": "¿Quién ganó el mundial de Qatar 2022?", "opciones": ["Argentina", "Francia", "Brasil"], "correcta": "Argentina"},
    {"pregunta": "¿Quién es el máximo goleador de la Selección Argentina?", "opciones": ["Messi", "Maradona", "Batistuta"], "correcta": "Messi"},
    {"pregunta": "¿Cuál es el estadio de Boca Juniors?", "opciones": ["La Bombonera", "El Monumental", "El Cilindro"], "correcta": "La Bombonera"},
    {"pregunta": "¿Qué equipo tiene más Copas Libertadores?", "opciones": ["Independiente", "Boca", "River"], "correcta": "Independiente"}
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
        url_goleadores = f"{url_base}/players/topscorers?league=128&season=2024"
        res_goleadores = requests.get(url_goleadores, headers=headers, timeout=4).json()
        if "response" in res_goleadores and isinstance(res_goleadores["response"], list):
            for item in res_goleadores["response"][:10]:
                player = item.get("player", {})
                stats = item.get("statistics", [{}])[0] if item.get("statistics") else {}
                datos_futbol["goleadores"].append({
                    "nombre": player.get("name", "Desconocido"),
                    "equipo": stats.get("team", {}).get("name", "Desconocido")
                })
    except Exception:
        pass
    return datos_futbol

app = FastAPI()

# --- RUTA 1: ENTRADA VISUAL ---
@app.get("/", response_class=HTMLResponse)
async def obtener_interfaz():
    ruta_html = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(ruta_html):
        with open(ruta_html, "r", encoding="utf-8") as archivo:
            return HTMLResponse(content=archivo.read(), status_code=200)
    return HTMLResponse(content="<h1>⚽ Servidor Activo</h1>", status_code=200)

# --- RUTA 2: ENDPOINT HTTP BAJO DEMANDA (Reemplaza al WebSocket) ---
@app.get("/api/trivias")
async def obtener_trivias_http():
    try:
        loop = asyncio.get_running_loop()
        contexto = await loop.run_in_executor(None, obtener_datos_futbol_real)
        
        # Si la API de fútbol no devolvió nada, usamos respaldo directo rápido
        if not contexto["goleadores"]:
            return {"preguntas": random.sample(BANCO_RESPALDO, len(BANCO_RESPALDO))}

        prompt_sistema = "Sos un experto en trivias de fútbol. Responde ÚNICAMENTE con un objeto JSON con un array de exactamente 40 preguntas bajo la clave 'preguntas'. Sin bloques Markdown."
        prompt_usuario = f"Basándote en estos datos: {json.dumps(contexto)} Genera un array de 40 preguntas de trivia con la estructura: pregunta, opciones, correcta."
        
        completion = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="grok-beta", 
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": prompt_usuario}],
                timeout=12
            )
        )
        datos = json.loads(completion.choices.message.content)
        if "preguntas" in datos and len(datos["preguntas"]) > 0:
            return {"preguntas": datos["preguntas"]}
    except Exception:
        pass
    
    # Caída segura de emergencia
    return {"preguntas": random.sample(BANCO_RESPALDO, len(BANCO_RESPALDO))}
