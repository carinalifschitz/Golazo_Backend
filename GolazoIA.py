import asyncio
import json
import os
import requests
import random
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

# --- CONFIGURACIÓN DE CREDENCIALES ---
GROK_API_KEY = os.environ.get("GROK_API_KEY", "TU_API_KEY_DE_GROK")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "TU_API_KEY_DE_API_FOOTBALL")

client = OpenAI(
    api_key=GROK_API_KEY, 
    base_url="https://x.ai"
)

# --- BANCO DE RESPALDO INTEGRADO ---
BANCO_RESPALDO = [
    {"pregunta": "¿Qué equipo se consagró campeón del mundo de clubes al vencer al Real Madrid en el año 2000?", "opciones": ["Boca Juniors", "River Plate", "Palmeiras"], "correcta": "Boca Juniors"},
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
        # Consultamos la temporada 2024 para garantizar datos reales estables
        url_goleadores = f"{url_base}/players/topscorers?league=128&season=2024"
        res_goleadores = requests.get(url_goleadores, headers=headers, timeout=4).json()
        if "response" in res_goleadores and isinstance(res_goleadores["response"], list):
            for item in res_goleadores["response"][:10]:
                player = item.get("player", {})
                stats_list = item.get("statistics", [])
                stats = stats_list[0] if isinstance(stats_list, list) and len(stats_list) > 0 else {}
                datos_futbol["goleadores"].append({
                    "nombre": player.get("name", "Desconocido"),
                    "equipo": stats.get("team", {}).get("name", "Desconocido")
                })
    except Exception:
        pass
    return datos_futbol

app = FastAPI()

# Configuración CORS para evitar bloqueos de peticiones HTTP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- RUTA 1: RENDERIZADO VISUAL ---
@app.get("/", response_class=HTMLResponse)
async def obtener_interfaz():
    ruta_html = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(ruta_html):
        with open(ruta_html, "r", encoding="utf-8") as archivo:
            return HTMLResponse(content=archivo.read(), status_code=200)
    return HTMLResponse(content="<h1>⚽ Servidor Golazo IA Activo (index.html no encontrado en la raíz)</h1>", status_code=200)

# --- RUTA 2: API HTTP BAJO DEMANDA ---
@app.get("/api/trivias")
async def obtener_trivias_http():
    try:
        loop = asyncio.get_running_loop()
        contexto = await loop.run_in_executor(None, obtener_datos_futbol_real)
        
        # Si la API de deportes no responde, usamos el banco nativo inmediatamente
        if not contexto.get("goleadores"):
            return {"preguntas": random.sample(BANCO_RESPALDO, len(BANCO_RESPALDO))}

        prompt_sistema = "Sos un experto en trivias de fútbol. Responde ÚNICAMENTE con un objeto JSON estructurado que contenga un array de exactamente 40 preguntas bajo la clave 'preguntas'. Sin bloques Markdown ni texto extra."
        prompt_usuario = f"Basándote en estos datos reales: {json.dumps(contexto)} Genera un array de exactamente 40 preguntas de trivia con estructura: pregunta, opciones, correcta."
        
        completion = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="grok-beta", 
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": prompt_usuario}],
                timeout=10  # Timeout estricto para evitar retrasar la respuesta web
            )
        )
        
        datos = json.loads(completion.choices.message.content)
        if "preguntas" in datos and len(datos["preguntas"]) > 0:
            return {"preguntas": datos["preguntas"]}
            
    except Exception:
        pass
    
    # Retorno seguro si falla la IA o expira el tiempo
    return {"preguntas": random.sample(BANCO_RESPALDO, len(BANCO_RESPALDO))}
