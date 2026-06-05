import asyncio
import json
import os
import requests
import random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# --- CONFIGURACIÓN DE CREDENCIALES DESDE RENDER ---
GROK_API_KEY = os.environ.get("GROK_API_KEY")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY")

# --- BANCO DE RESPALDO INTEGRADO (40 PREGUNTAS COMPLETAS SOBRE QATAR 2022) ---
BANCO_RESPALDO = [
    {"pregunta": "¿Cuál fue el resultado final tras los 120 minutos en la final de Qatar 2022 antes de los penales?", "opciones": ["3-3", "2-2", "4-4"], "correcta": "3-3"},
    {"pregunta": "¿Qué jugador argentino anotó el primer gol de la final de Qatar 2022 de penal?", "opciones": ["Lionel Messi", "Ángel Di María", "Julián Álvarez"], "correcta": "Lionel Messi"},
    {"pregunta": "¿Quién anotó un Hat-Trick para Francia en la final de Qatar 2022?", "opciones": ["Kylian Mbappé", "Antoine Griezmann", "Olivier Giroud"], "correcta": "Kylian Mbappé"},
    {"pregunta": "¿Qué arquero ganó el Guante de Oro tras su icónica atajada a Kolo Muani en el último minuto?", "opciones": ["Emiliano Martínez", "Hugo Lloris", "Yassine Bounou"], "correcta": "Emiliano Martínez"},
    {"pregunta": "¿Qué jugador anotó el penal definitivo que consagró campeona a Argentina?", "opciones": ["Gonzalo Montiel", "Leandro Paredes", "Paulo Dybala"], "correcta": "Gonzalo Montiel"},
    {"pregunta": "¿Quién asistió a Ángel Di María para el segundo gol argentino en una contra perfecta?", "opciones": ["Alexis Mac Allister", "Lionel Messi", "Rodrigo de Paul"], "correcta": "Alexis Mac Allister"},
    {"pregunta": "¿En qué estadio se disputó la gran final entre Argentina y Francia?", "opciones": ["Estadio de Lusail", "Estadio Al Bayt", "Estadio Al Thumama"], "correcta": "Estadio de Lusail"},
    {"pregunta": "¿Quién era el director técnico de la Selección Argentina en Qatar 2022?", "opciones": ["Lionel Scaloni", "Gerardo Martino", "Jorge Sampaoli"], "correcta": "Lionel Scaloni"},
    {"pregunta": "¿Cuántos penales atajó el 'Dibu' Martínez en la tanda definitoria de la final?", "opciones": ["1", "2", "3"], "correcta": "1"},
    {"pregunta": "¿Qué jugador francés desvió su tiro penal afuera en la tanda de penales?", "opciones": ["Aurélien Tchouaméni", "Kingsley Coman", "Randal Kolo Muani"], "correcta": "Aurélien Tchouaméni"},
    {"pregunta": "¿En qué año se disputó el Mundial de Qatar?", "opciones": ["2022", "2018", "2020"], "correcta": "2022"},
    {"pregunta": "¿Qué jugador francés usa la camiseta número 10?", "opciones": ["Kylian Mbappé", "Antoine Griezmann", "Olivier Giroud"], "correcta": "Kylian Mbappé"},
    {"pregunta": "¿Quién abrió la tanda de penales para Argentina en la final?", "opciones": ["Lionel Messi", "Paulo Dybala", "Leandro Paredes"], "correcta": "Lionel Messi"},
    {"pregunta": "¿Quién fue elegido el mejor jugador joven del Mundial Qatar 2022?", "opciones": ["Enzo Fernández", "Julián Álvarez", "Aurélien Tchouaméni"], "correcta": "Enzo Fernández"},
    {"pregunta": "¿Qué jugador argentino juega con la camiseta número 11?", "opciones": ["Ángel Di María", "Lionel Messi", "Lautaro Martínez"], "correcta": "Ángel Di María"},
    {"pregunta": "¿Qué selección africana eliminó a Portugal y llegó a semis?", "opciones": ["Marruecos", "Camerún", "Senegal"], "correcta": "Marruecos"},
    {"pregunta": "¿Qué país se quedó con el tercer puesto en Qatar 2022?", "opciones": ["Croacia", "Marruecos", "Francia"], "correcta": "Croacia"},
    {"pregunta": "¿Contra qué selección debutó Argentina perdiendo 2-1?", "opciones": ["Arabia Saudita", "México", "Polonia"], "correcta": "Arabia Saudita"},
    {"pregunta": "¿Quién metió el golazo de tiro libre de Países Bajos en el último minuto de descuento contra Argentina?", "opciones": ["Wout Weghorst", "Memphis Depay", "Virgil van Dijk"], "correcta": "Wout Weghorst"},
    {"pregunta": "¿Qué jugador argentino asistió a Nahuel Molina contra Países Bajos sin mirar?", "opciones": ["Lionel Messi", "Ángel Di María", "Enzo Fernández"], "correcta": "Lionel Messi"},
    {"pregunta": "¿Cuántas Copas del Mundo tiene la Selección Argentina con la de 2022?", "opciones": ["3", "2", "4"], "correcta": "3"},
    {"pregunta": "¿Qué selección defendía el título de campeón en Qatar 2022?", "opciones": ["Francia", "Alemania", "Brasil"], "correcta": "Francia"},
    {"pregunta": "¿En qué mes se jugó la final de Qatar 2022?", "opciones": ["Diciembre", "Julio", "Junio"], "correcta": "Diciembre"},
    {"pregunta": "¿Quién metió el primer gol de Argentina en la semifinal contra Croacia?", "opciones": ["Lionel Messi", "Julián Álvarez", "Rodrigo de Paul"], "correcta": "Lionel Messi"},
    {"pregunta": "¿Cuántos goles hizo Julián Álvarez en la semifinal contra Croacia?", "opciones": ["2", "1", "3"], "correcta": "2"},
    {"pregunta": "¿Qué marca de ropa vistió a la Selección Argentina campeona en 2022?", "opciones": ["Adidas", "Nike", "Puma"], "correcta": "Adidas"},
    {"pregunta": "¿Qué jugador polaco, delantero del Barcelona, enfrentó a Argentina en fase de grupos?", "opciones": ["Robert Lewandowski", "Arkadiusz Milik", "Piotr Zieliński"], "correcta": "Robert Lewandowski"},
    {"pregunta": "¿Quién metió el segundo gol de Argentina contra México desde afuera del área?", "opciones": ["Enzo Fernández", "Lionel Messi", "Alexis Mac Allister"], "correcta": "Enzo Fernández"},
    {"pregunta": "¿Quién era el capitán de la Selección de Francia en la final?", "opciones": ["Hugo Lloris", "Raphaël Varane", "Antoine Griezmann"], "correcta": "Hugo Lloris"},
    {"pregunta": "¿A qué selección eliminó Francia en las semifinales de Qatar 2022?", "opciones": ["Marruecos", "Inglaterra", "Polonia"], "correcta": "Marruecos"},
    {"pregunta": "¿Qué jugador argentino fue expulsado en el torneo?", "opciones": ["Ninguno", "Leandro Paredes", "Marcos Acuña"], "correcta": "Ninguno"},
    {"pregunta": "¿Qué número usó Julián Álvarez en Qatar 2022?", "opciones": ["9", "22", "19"], "correcta": "9"},
    {"pregunta": "¿Quién hizo el gol de la victoria 2-1 de Argentina contra Australia en octavos?", "opciones": ["Julián Álvarez", "Lionel Messi", "Enzo Fernández"], "correcta": "Julián Álvarez"},
    {"pregunta": "¿Qué árbitro dirigió la final de Qatar 2022 entre Argentina y Francia?", "opciones": ["Szymon Marciniak", "Mateu Lahoz", "Wilton Sampaio"], "correcta": "Szymon Marciniak"},
    {"pregunta": "¿Qué jugador francés de la final jugaba en el Atlético de Madrid?", "opciones": ["Antoine Griezmann", "Ousmane Dembélé", "Adrien Rabiot"], "correcta": "Antoine Griezmann"},
    {"pregunta": "¿Cuál era el nombre de la pelota oficial de las semifinales y la final?", "opciones": ["Al Hilm", "Al Rihla", "Jabulani"], "correcta": "Al Hilm"},
    {"pregunta": "¿Cuántos goles totales hizo Lionel Messi en el Mundial de Qatar 2022?", "opciones": ["7", "8", "6"], "correcta": "7"},
    {"pregunta": "¿Quién ganó el premio al Balón de Oro como mejor jugador del torneo?", "opciones": ["Lionel Messi", "Kylian Mbappé", "Luka Modrić"], "correcta": "Lionel Messi"},
    {"pregunta": "¿Qué jugador de Francia fue reemplazado en el primer tiempo de la final?", "opciones": ["Olivier Giroud", "Antoine Griezmann", "Kylian Mbappé"], "correcta": "Olivier Giroud"},
    {"pregunta": "¿Cuál fue el resultado de la tanda de penales a favor de Argentina en la final?", "opciones": ["4-2", "3-1", "4-3"], "correcta": "4-2"}
]

def obtener_datos_final_mundo():
    # CORRECCIÓN: Usamos la URL y Host de RapidAPI autorizados para saltar el Firewall perimetral
    url_base = "https://rapidapi.com"
    headers = {
        "X-RapidAPI-Host": "://rapidapi.com",
        "X-RapidAPI-Key": FOOTBALL_API_KEY if FOOTBALL_API_KEY else "",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    datos_partido = {"detalles": {}, "eventos": []}
    
    print("[DIAGNÓSTICO] ---> 1. Llamando a API-Football mediante pasarela RapidAPI...")
    try:
        url_fixture = f"{url_base}/fixtures?id=970030"
        res = requests.get(url_fixture, headers=headers, timeout=5)
        
        print(f"[DIAGNÓSTICO] API-Football respondió con Código HTTP: {res.status_code}")
        
        if res.status_code == 200:
            datos_json = res.json()
            if "response" in datos_json and len(datos_json["response"]) > 0:
                partido = datos_json["response"][0]
                
                datos_partido["detalles"] = {
                    "local": partido["teams"]["home"]["name"],
                    "visitante": partido["teams"]["away"]["name"],
                    "goles_local": partido["goals"]["home"],
                    "goles_visitante": partido["goals"]["away"],
                    "estadio": partido["fixture"]["venue"]["name"],
                    "arbitro": partido["fixture"]["referee"]
                }
                
                for evento in partido.get("events", [])[:20]:
                    datos_partido["eventos"].append({
                        "tiempo": evento["time"]["elapsed"],
                        "equipo": evento["team"]["name"],
                        "jugador": evento["player"]["name"] if evento.get("player") else "Desconocido",
                        "tipo": evento["type"],
                        "detalle": evento["detail"]
                    })
                print(f"[DIAGNÓSTICO] API-Football exitosa. Se guardó el JSON con {len(datos_partido['eventos'])} eventos del partido.")
        else:
            print(f"[ALERTA API-FÚTBOL] Error de red en la pasarela: {res.status_code}")
            
    except Exception as e:
        print(f"[ALERTA API-FÚTBOL] Excepción de conexión: {e}")
        
    return datos_partido

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def obtener_interfaz(request: Request):
    ruta_html = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(ruta_html):
        with open(ruta_html, "r", encoding="utf-8") as archivo:
            return HTMLResponse(content=archivo.read(), status_code=200)
    return HTMLResponse(content="<h1>⚽ Servidor Golazo IA Activo</h1>", status_code=200)

@app.get("/api/trivias")
async def obtener_trivias_http():
    print("\n================== NUEVA PETICIÓN DE TRIVIA ==================")
    
    # Declaramos las variables locales al inicio de la función de forma segura
    loop = asyncio.get_running_loop()
    contexto_mundial = {"detalles": {}, "eventos": []}
    
    if not GROK_API_KEY:
        print("[ALERTA GROK] La variable GROK_API_KEY está vacía en el panel de Render.")
        copia_respaldo = list(BANCO_RESPALDO)
        random.shuffle(copia_respaldo)
        return {"preguntas": copia_respaldo}

    # 1. Consumir el JSON real de la final usando el executor asíncrono
    try:
        contexto_mundial = await loop.run_in_executor(None, obtener_datos_final_mundo)
    except Exception as e:
        print(f"[ALERTA LOOP] Error en executor asíncrono: {e}")
    
    # Resguardo integrado por si tu plan gratuito de la API no tiene requests disponibles
    if not contexto_mundial or not contexto_mundial.get("detalles"):
        print("[DIAGNÓSTICO] Usando JSON real de respaldo de la Final de Qatar 2022.")
        contexto_mundial = {
            "detalles": {"local": "Argentina", "visitante": "Francia", "goles_local": 3, "goles_visitante": 3, "estadio": "Lusail Iconic Stadium", "arbitro": "Szymon Marciniak"},
            "eventos": [
                {"tiempo": 23, "equipo": "Argentina", "jugador": "Lionel Messi", "tipo": "Goal", "detalle": "Penalty"},
                {"tiempo": 36, "equipo": "Argentina", "jugador": "Ángel Di María", "tipo": "Goal", "detalle": "Normal Goal"},
                {"tiempo": 80, "equipo": "Francia", "jugador": "Kylian Mbappé", "tipo": "Goal", "detalle": "Penalty"},
                {"tiempo": 81, "equipo": "Francia", "jugador": "Kylian Mbappé", "tipo": "Goal", "detalle": "Normal Goal"},
                {"tiempo": 108, "equipo": "Argentina", "jugador": "Lionel Messi", "tipo": "Goal", "detalle": "Normal Goal"},
                {"tiempo": 118, "equipo": "Francia", "jugador": "Kylian Mbappé", "tipo": "Goal", "detalle": "Penalty"}
            ]
        }

    # 2. Mandar ese JSON extraído directo al prompt de Grok-2
    try:
        url_grok = "https://x.ai"
        headers_grok = {
            "Authorization": f"Bearer {GROK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt_sistema = (
            "Sos un historiador deportivo experto en Copas del Mundo. Tu única tarea es responder con un objeto JSON válido. "
            "Este JSON debe tener una clave única llamada 'preguntas' que contenga un array de exactamente 40 objetos. "
            "No devuelvas bloques Markdown (```json) ni texto explicativo extra."
        )
        prompt_usuario = (
            f"Basándote estrictamente en este JSON con datos reales de la Final de Qatar 2022 extraídos de la API: {json.dumps(contexto_mundial, ensure_ascii=False)}. "
            "Generá un array de exactamente 40 preguntas de trivia variadas sobre este partido. "
            "Muchas preguntas deben interrogar sobre los minutos exactos de los goles, quién los metió, el árbitro, el estadio y los detalles provistos en el JSON. "
            "Estructura requerida por objeto del array: pregunta, opciones (array de 3 strings), correcta (debe coincidir exactamente con una opción)."
        )

        payload = {
            "model": "grok-2", 
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            "temperature": 0.7
        }

        print("[DIAGNÓSTICO] ---> 2. Enviando JSON del partido al servidor de Grok (x.ai)...")
        res = requests.post(url_grok, json=payload, headers=headers_grok, timeout=15)
        
        print(f"[DIAGNÓSTICO] Grok respondió con Código HTTP: {res.status_code}")
        
        if res.status_code == 200:
            datos_api = res.json()
            texto_json = datos_api["choices"]["message"]["content"]
            datos_finales = json.loads(texto_json)
            
            if "preguntas" in datos_finales and len(datos_finales["preguntas"]) > 0:
                print(f"[DIAGNÓSTICO] ¡Éxito total! Grok leyó el JSON de la API y armó {len(datos_finales['preguntas'])} preguntas dinámicas.")
                preguntas_mezcladas = datos_finales["preguntas"]
                random.shuffle(preguntas_mezcladas)
                return {"preguntas": preguntas_mezcladas}
        else:
            print(f"[ALERTA GROK] La API rechazó el token o el saldo. Respuesta exacta: {res.text}")
            
    except Exception as e:
        print(f"[ALERTA GROK] Error crítico de procesamiento: {e}")
    
    print("[SERVER] Flujo terminado. Entregando el mazo por defecto temático de Qatar 2022.")
    copia_respaldo = list(BANCO_RESPALDO)
    random.shuffle(copia_respaldo)
    return {"preguntas": copia_respaldo}

