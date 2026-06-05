import json
import os
import requests
import random
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# --- CONFIGURACIÓN DE CREDENCIALES DESDE RENDER ---
# os.environ.get lee los valores exactos que configuraste en la pestaña Environment Variables
GROK_API_KEY = os.environ.get("GROK_API_KEY")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY")

# --- BANCO DE RESPALDO INTEGRADO (40 PREGUNTAS COMPLETAS) ---
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
    {"pregunta": "¿Cuál de estos equipos NO descendió nunca de la Primera División de Argentina?", "opciones": ["Boca Juniors", "River Plate", "Independiente"], "correcta": "Boca Juniors"},
    {"pregunta": "¿En qué club de España jugó Juan Román Riquelme además del Barcelona?", "opciones": ["Villarreal", "Sevilla", "Valencia"], "correcta": "Villarreal"},
    {"pregunta": "¿Quién fue el máximo goleador del Mundial de Qatar 2022?", "opciones": ["Kylian Mbappé", "Lionel Messi", "Julián Álvarez"], "correcta": "Kylian Mbappé"},
    {"pregunta": "¿Qué equipo argentino ganó más Copas Libertadores?", "opciones": ["Independiente", "Boca Juniors", "River Plate"], "correcta": "Independiente"},
    {"pregunta": "¿Qué jugador argentino anotó dos goles en la final de la Champions 2010 con el Inter?", "opciones": ["Diego Milito", "Javier Zanetti", "Esteban Cambiasso"], "correcta": "Diego Milito"},
    {"pregunta": "¿En qué año se inauguró el Estadio Alberto J. Armando (La Bombonera)?", "opciones": ["1940", "1950", "1931"], "correcta": "1940"},
    {"pregunta": "¿Cuál fue el resultado de la final del Mundial Alemania 2006 en los 120 minutos?", "opciones": ["1-1", "0-0", "2-1"], "correcta": "1-1"},
    {"pregunta": "¿Qué futbolista es conocido mundialmente como 'O Rei'?", "opciones": ["Pelé", "Maradona", "Ronaldinho"], "correcta": "Pelé"},
    {"pregunta": "¿Qué país ganó la primera Copa Mundial de la FIFA en 1930?", "opciones": ["Uruguay", "Argentina", "Brasil"], "correcta": "Uruguay"},
    {"pregunta": "¿Quién es el máximo goleador histórico de los mundiales?", "opciones": ["Miroslav Klose", "Ronaldo Nazário", "Gerd Müller"], "correcta": "Miroslav Klose"},
    {"pregunta": "¿Qué club inglés tiene más títulos de la UEFA Champions League?", "opciones": ["Liverpool", "Manchester United", "Chelsea"], "correcta": "Liverpool"},
    {"pregunta": "¿Quién ganó la Eurocopa en el año 2024?", "opciones": ["España", "Inglaterra", "Francia"], "correcta": "España"},
    {"pregunta": "¿En qué club francés jugó Lionel Messi tras salir del Barcelona?", "opciones": ["PSG", "Marsella", "Mónaco"], "correcta": "PSG"},
    {"pregunta": "¿Qué país organizó el Mundial de fútbol de 1978?", "opciones": ["Argentina", "Brasil", "México"], "correcta": "Argentina"},
    {"pregunta": "¿Cómo se llama el trofeo que se entrega al campeón de la liga española?", "opciones": ["Trofeo de LaLiga", "Copa del Rey", "Copa de la Reina"], "correcta": "Trofeo de LaLiga"},
    {"pregunta": "¿Qué selección africana fue la primera en llegar a una semifinal del Mundo?", "opciones": ["Marruecos", "Camerún", "Senegal"], "correcta": "Marruecos"},
    {"pregunta": "¿Quién es el máximo goleador histórico de la UEFA Champions League?", "opciones": ["Cristiano Ronaldo", "Lionel Messi", "Robert Lewandowski"], "correcta": "Cristiano Ronaldo"},
    {"pregunta": "¿En qué país se juega el clásico entre Celtic y Rangers?", "opciones": ["Escocia", "Irlanda", "Gales"], "correcta": "Escocia"},
    {"pregunta": "¿Qué club de fútbol argentino es conocido como 'La Academia'?", "opciones": ["Racing Club", "San Lorenzo", "Estudiantes"], "correcta": "Racing Club"},
    {"pregunta": "¿Qué número de camiseta usaba Zinedine Zidane en el Real Madrid?", "opciones": ["5", "10", "7"], "correcta": "5"},
    {"pregunta": "¿Quién es el dueño del arco de la Selección Argentina apodado 'Dibu'?", "opciones": ["Emiliano Martínez", "Franco Armani", "Gerónimo Rulli"], "correcta": "Emiliano Martínez"},
    {"pregunta": "¿Qué equipo italiano es conocido popularmente como 'La Vecchia Signora'?", "opciones": ["Juventus", "AC Milan", "Inter"], "correcta": "Juventus"},
    {"pregunta": "¿En qué ciudad de Estados Unidos juega actualmente Lionel Messi?", "opciones": ["Miami", "Los Angeles", "New York"], "correcta": "Miami"},
    {"pregunta": "¿Qué selección nacional eliminó a Argentina en el Mundial de Rusia 2018?", "opciones": ["Francia", "Croacia", "Nigeria"], "correcta": "Francia"},
    {"pregunta": "¿Cuál es el apodo oficial de la Selección de fútbol de Uruguay?", "opciones": ["La Celeste", "La Charrúa", "La Garra"], "correcta": "La Celeste"},
    {"pregunta": "¿Qué club alemán juega sus partidos de local en el Allianz Arena?", "opciones": ["Bayern Múnich", "Borussia Dortmund", "Bayer Leverkusen"], "correcta": "Bayern Múnich"},
    {"pregunta": "¿Quién ganó la Copa América celebrada en el año 2021?", "opciones": ["Argentina", "Brasil", "Colombia"], "correcta": "Argentina"},
    {"pregunta": "¿Cómo le dicen popularmente al club argentino Rosario Central?", "opciones": ["El Canalla", "El Leproso", "El Pincha"], "correcta": "El Canalla"},
    {"pregunta": "¿Qué selección ganó el Mundial de Sudáfrica 2010?", "opciones": ["España", "Países Bajos", "Alemania"], "correcta": "España"},
    {"pregunta": "¿Quién es el jugador con más partidos disputados en la historia de los Mundiales?", "opciones": ["Lionel Messi", "Lothar Matthäus", "Miroslav Klose"], "correcta": "Lionel Messi"},
    {"pregunta": "¿Qué club del fútbol argentino juega en el Estadio Libertadores de América?", "opciones": ["Independiente", "Racing", "Arsenal"], "correcta": "Independiente"}
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
                datos_futbol["goleadores"].append({
                    "nombre": player.get("name", "Desconocido")
                })
    except Exception:
        pass
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
    # Validación preventiva por si las variables no se leyeron bien
    if not GROK_API_KEY:
        print("Aviso: GROK_API_KEY está vacía en Render. Usando banco harcodeado.")
        return {"questions": random.sample(BANCO_RESPALDO, len(BANCO_RESPALDO))}

    try:
        url_grok = "https://x.ai"
        headers_grok = {
            "Authorization": f"Bearer {GROK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        loop = asyncio.get_running_loop()
        contexto = await loop.run_in_executor(None, obtener_datos_futbol_real)
        
        prompt_sistema = "Sos un experto en trivias de fútbol. Responde ÚNICAMENTE con un objeto JSON válido que contenga un array de exactamente 40 preguntas bajo la clave 'preguntas'. No uses bloques de código Markdown ni texto extra."
        prompt_usuario = f"Basándote en estos datos reales: {json.dumps(contexto)} Genera un array de exactamente 40 preguntas de trivia variadas sobre fútbol internacional y argentino de los últimos años. Estructura requerida: pregunta, opciones (array de 3 strings), correcta (debe coincidir exactamente con una de las opciones)."

        payload = {
            "model": "grok-beta",
