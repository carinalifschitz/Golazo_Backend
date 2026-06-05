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
# Reemplazá estos textos con tus claves reales si querés usar la Inteligencia Artificial
GROK_API_KEY = os.environ.get("GROK_API_KEY", "TU_API_KEY_DE_GROK")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "TU_API_KEY_DE_API_FOOTBALL")

client = OpenAI(
    api_key=GROK_API_KEY, 
    base_url="https://xai.tech"
)

# --- VARIABLES DE CONTROL Y BANCO DE TRIVIAS NATIVO (40 PREGUNTAS) ---
BANCO_TRIVIAS = [
    {"pregunta": "¿Qué equipo se consagró campeón del mundo de clubes al vencer al Real Madrid en el año 2000?", "opciones": ["Boca Juniors", "River Plate", "Palmeiras"], "correcta": "Boca Juniors"},
    {"pregunta": "¿Quién es el máximo goleador histórico de la Selección Argentina?", "opciones": ["Lionel Messi", "Gabriel Batistuta", "Diego Maradona"], "correcta": "Lionel Messi"},
    {"pregunta": "¿En qué club europeo debutó profesionalmente Sergio 'Kun' Agüero?", "opciones": ["Atlético de Madrid", "Manchester City", "Barcelona"], "correcta": "Atlético de Madrid"},
    {"pregunta": "¿Quién fue el director técnico de la Selección Argentina en el Mundial de Sudáfrica 2010?", "opciones": ["Diego Maradona", "Alejandro Sabella", "Alfio Basile"], "correcta": "Diego Maradona"},
    {"pregunta": "¿Qué país organizó y ganó el Mundial de fútbol de 1998?", "opciones": ["Francia", "Brasil", "Italia"], "correcta": "Francia"},
    {"pregunta": "¿Cuál es el estadio de fútbol con mayor capacidad de espectadores en Sudamérica?", "opciones": ["Estadio Mâs Monumental", "Estadio Maracaná", "Estadio Centenario"], "correcta": "Estadio Mâs Monumental"},
    {"pregunta": "¿Quién anotó el famoso gol conocido como 'La mano de Dios' en 1986?", "opciones": ["Diego Maradona", "Jorge Burruchaga", "Gary Lineker"], "correcta": "Diego Maradona"},
    {"pregunta": "¿Qué club de la Liga Argentina es conocido popularmente como 'El Taladro'?", "opciones": ["Banfield", "Lanús", "Temperley"], "correcta": "Banfield"},
    {"pregunta": "¿Quién ganó el Balón de Oro de la FIFA en el año 2023?", "opciones": ["Lionel Messi", "Erling Haaland", "Kylian Mbappé"], "correcta": "Lionel Messi"},
    {"pregunta": "¿Cuál de estos equipos NO descendió nunca de la Primera División de Argentina?", "opciones": ["Boca Juniors", "River Plate", "Independiente"], "correcta": "Boca Juniors"},
    {"pregunta": "¿En qué club de España jugó el mediocampista Juan Román Riquelme además del Barcelona?", "opciones": ["Villarreal", "Sevilla", "Valencia"], "correcta": "Villarreal"},
    {"pregunta": "¿Quién fue el goleador del Mundial de Qatar 2022?", "opciones": ["Kylian Mbappé", "Lionel Messi", "Julián Álvarez"], "correcta": "Kylian Mbappé"},
    {"pregunta": "¿Qué equipo del fútbol argentino tiene el récord de más campeonatos de Copa Libertadores ganados?", "opciones": ["Independiente", "Boca Juniors", "Estudiantes de La Plata"], "correcta": "Independiente"},
    {"pregunta": "¿Qué jugador argentino ganó la Champions League con el Inter de Milán anotando dos goles en la final de 2010?", "opciones": ["Diego Milito", "Javier Zanetti", "Esteban Cambiasso"], "correcta": "Diego Milito"},
    {"pregunta": "¿En qué año se inauguró el actual Estadio Alberto J. Armando, conocido como La Bombonera?", "opciones": ["1940", "1950", "1931"], "correcta": "1940"},
    {"pregunta": "¿Cuál fue el resultado de la final del Mundial de Alemania 2006 entre Italia y Francia en los 120 minutos?", "opciones": ["1-1", "0-0", "2-1"], "correcta": "1-1"},
    {"pregunta": "¿Qué futbolista es conocido mundialmente como 'O Rei'?", "opciones": ["Pelé", "Garrincha", "Ronaldinho"], "correcta": "Pelé"},
    {"pregunta": "¿Quién es el director técnico actual de la Selección Mayor de Argentina?", "opciones": ["Lionel Scaloni", "Jorge Sampaoli", "Gerardo Martino"], "correcta": "Lionel Scaloni"},
    {"pregunta": "¿Qué club inglés es conocido como los 'Red Devils'?", "opciones": ["Manchester United", "Liverpool", "Arsenal"], "correcta": "Manchester United"},
    {"pregunta": "¿En qué club de la MLS juega actualmente el capitán argentino Lionel Messi?", "opciones": ["Inter Miami", "LA Galaxy", "New York City FC"], "correcta": "Inter Miami"},
    {"pregunta": "¿Qué número de camiseta usó principalmente Ángel Di María en la Selección Argentina?", "opciones": ["11", "7", "10"], "correcta": "11"},
    {"pregunta": "¿Contra qué país debutó oficialmente Diego Maradona en un Mundial de Fútbol (España 1982)?", "opciones": ["Bélgica", "Hungría", "El Salvador"], "correcta": "Bélgica"},
    {"pregunta": "¿Cuál de estos países ha ganado exactamente CUATRO copas mundiales de la FIFA?", "opciones": ["Alemania", "Brasil", "Argentina"], "correcta": "Alemania"},
    {"pregunta": "¿Qué jugador pateó el penal decisivo contra Francia en la final del mundo de Qatar 2022?", "opciones": ["Gonzalo Montiel", "Leandro Paredes", "Lautaro Martínez"], "correcta": "Gonzalo Montiel"},
    {"pregunta": "¿Qué histórico defensor argentino es apodado 'El Ratón'?", "opciones": ["Roberto Ayala", "Walter Samuel", "Gabriel Heinze"], "correcta": "Roberto Ayala"},
    {"pregunta": "¿Qué club de fútbol de Córdoba es apodado 'El Pirata'?", "opciones": ["Belgrano", "Talleres", "Instituto"], "correcta": "Belgrano"},
    {"pregunta": "¿Cuál es el clásico rival histórico de San Lorenzo de Almagro?", "opciones": ["Huracán", "Velez Sarsfield", "Ferro"], "correcta": "Huracán"},
    {"pregunta": "¿Quién es el arquero titular de la Selección Argentina campeona del mundo en 2022?", "opciones": ["Emiliano Martínez", "Franco Armani", "Gerónimo Rulli"], "correcta": "Emiliano Martínez"},
    {"pregunta": "¿En qué país se disputó la Copa del Mundo de 1994?", "opciones": ["Estados Unidos", "México", "Italia"], "correcta": "Estados Unidos"},
    {"pregunta": "¿Qué club de Primera División tiene su estadio bautizado como 'Libertadores de América'?", "opciones": ["Independiente", "Racing Club", "Estudiantes de La Plata"], "correcta": "Independiente"},
    {"pregunta": "¿Quién fue el arquero de la Selección Argentina en la final del Mundial de Brasil 2014?", "opciones": ["Sergio Romero", "Mariano Andújar", "Agustín Orion"], "correcta": "Sergio Romero"},
    {"pregunta": "¿Qué jugador convirtió el gol agónico de River contra Boca en la final de Madrid 2018 para poner el 3-1?", "opciones": ["Gonzalo Martínez", "Juan Fernando Quintero", "Lucas Pratto"], "correcta": "Gonzalo Martínez"},
    {"pregunta": "¿Qué selección sudamericana es apodada tradicionalmente 'La Vinotinto'?", "opciones": ["Venezuela", "Ecuador", "Bolivia"], "correcta": "Venezuela"},
    {"pregunta": "¿Quién tiene el récord de más goles anotados en un solo Mundial de fútbol (13 goles en 1958)?", "opciones": ["Just Fontaine", "Gerd Müller", "Pelé"], "correcta": "Just Fontaine"},
    {"pregunta": "¿A qué club argentino pertenece el Estadio Ciudad de Vicente López?", "opciones": ["Platense", "Tigre", "Chacarita"], "correcta": "Platense"},
    {"pregunta": "¿Qué país africano logró por primera vez en la historia llegar a las semifinales de un Mundial en Qatar 2022?", "opciones": ["Marruecos", "Senegal", "Camerún"], "correcta": "Marruecos"},
    {"pregunta": "¿Qué futbolista argentino ganó el premio al Mejor Jugador Joven del Mundial de Qatar 2022?", "opciones": ["Enzo Fernández", "Julián Álvarez", "Alexis Mac Allister"], "correcta": "Enzo Fernández"},
    {"pregunta": "¿Cuál de estos estadios se encuentra en la ciudad de Rosario?", "opciones": ["Coloso del Parque", "Estadio Mario Kempes", "Estadio Único"], "correcta": "Coloso del Parque"},
    {"pregunta": "¿Cuántas Copas del Mundo de la FIFA ha ganado la Selección Italiana hasta el momento?", "opciones": ["4", "3", "5"], "correcta": "4"},
    {"pregunta": "¿Quién es el máximo goleador histórico de los mundiales de fútbol masculinos con 16 goles?", "opciones": ["Miroslav Klose", "Ronaldo Nazário", "Gerd Müller"], "correcta": "Miroslav Klose"}
]

INDICE_INDIVIDUAL = {}
jugadores_esperando = []
salas_activas = {}
RANKING_GLOBAL = {}

# ----------------------------------------------------------------
# LÓGICA DE DATOS & INTELIGENCIA ARTIFICIAL (ENDPOINT CORREGIDO)
# ----------------------------------------------------------------

def consultar_api_futbol_masivo():
    """Consulta los últimos partidos apuntando al endpoint real de API-Sports."""
    url = "https://api-sports.io"
    querystring = {"last": "40", "status": "FT"}
    headers = {
        'x-apisports-key': FOOTBALL_API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    try:
        print("[API FÚTBOL]: Intentando conectar al servicio externo...")
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        print(f"[API FÚTBOL]: Código de respuesta HTTP {response.status_code}")
        
        data = response.json()
        if "errors" in data and data["errors"]:
            print(f"[API FÚTBOL]: Error reportado por el proveedor -> {data['errors']}")
            return None
            
        if data and data.get('response') and len(data['response']) > 0:
            print(f"[API FÚTBOL]: Éxito. Se descargaron {len(data['response'])} partidos reales.")
            return data['response']
        else:
            print("[API FÚTBOL]: Servidor respondió con un array de partidos vacío.")
    except Exception as e:
        print(f"[API FÚTBOL]: Error de conexión/timeout -> {e}")
    return None

def generar_trivia_de_partido(partido_raw):
    """Envía el JSON del partido a Grok para formatear una pregunta válida."""
    partido_string = json.dumps(partido_raw)
    prompt = f"""
    Basándote estrictamente en los datos estructurados de este partido de fútbol en formato JSON:
    {partido_string}
    Generá UNA pregunta de trivia que sea sumamente variada y específica. 
