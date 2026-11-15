"""
Datos reales de la NASA usados en el juego.

IMPORTANTE: son datos HISTÓRICOS guardados dentro del juego, no datos en tiempo real.
El juego debe presentarlos siempre como "evento real del pasado", nunca como "en vivo".

Llamaradas solares — fuente: NASA DONKI (Space Weather Database Of Notifications, Knowledge, Information)
    https://kauai.ccmc.gsfc.nasa.gov/DONKI/
    API: https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/FLR?startDate=AAAA-MM-DD&endDate=AAAA-MM-DD

PENDIENTE DE VERIFICAR: esta lista se capturó a mano (el servidor de DONKI no respondió al
descargarla). Antes de la entrega, compara cada fecha, clase y región activa con la API de arriba
y corrige lo que no coincida. Si se agrega una llamarada, copia los valores tal cual vienen en DONKI.
"""

# Cada llamarada: fecha (UTC), clase (escala real: C < M < X; el número multiplica la fuerza),
# región activa del Sol donde se originó y un dato real para mostrar al jugador.
SOLAR_FLARES = [
    {
        "date": "2017-09-06",
        "class": "X9.3",
        "region": 2673,
        "fact": "Fue la llamarada más fuerte del ciclo solar 24, el ciclo de actividad del Sol entre 2008 y 2019.",
    },
    {
        "date": "2017-09-10",
        "class": "X8.2",
        "region": 2673,
        "fact": "Sus partículas llegaron a Marte: el rover Curiosity midió que la radiación en la superficie "
                "se duplicó y la nave MAVEN vio auroras en el cielo marciano.",
    },
    {
        "date": "2024-05-11",
        "class": "X5.8",
        "region": 3664,
        "fact": "La región 3664 causó en mayo de 2024 la tormenta geomagnética más fuerte en la Tierra en "
                "más de 20 años; se vieron auroras en lugares donde casi nunca aparecen.",
    },
    {
        "date": "2024-05-14",
        "class": "X8.7",
        "region": 3664,
        "fact": "Unos días después, esa misma región mandó partículas hacia Marte: Curiosity midió una dosis "
                "parecida a la de 30 radiografías de tórax.",
    },
    {
        "date": "2024-10-01",
        "class": "X7.1",
        "region": 3842,
        "fact": "Las llamaradas clase X son las más fuertes: en su punto máximo, una X7 brilla en rayos X "
                "unas 70 veces más que una clase M1.",
    },
    {
        "date": "2024-10-03",
        "class": "X9.0",
        "region": 3842,
        "fact": "Fue una de las llamaradas más fuertes del ciclo solar 25, que empezó en 2019.",
    },
]

# Datos generales sobre la radiación en Marte (fuente: misión Curiosity, instrumento RAD, NASA/JPL).
MARS_RADIATION_FACTS = [
    "Marte no tiene un campo magnético global ni una atmósfera gruesa como la Tierra, "
    "por eso la radiación del Sol y del espacio llega casi directo a su superficie.",
    "El instrumento RAD del rover Curiosity mide la radiación en la superficie de Marte "
    "desde 2012: unos 0.7 milisieverts por día, mucho más que en la Tierra.",
]

# Plantas cultivadas en la Estación Espacial Internacional (fuente: NASA, sistemas Veggie y Advanced Plant Habitat).
# Los datos de experimentos con plantas en el espacio están en el NASA Open Science Data Repository (OSDR):
#     https://osdr.nasa.gov
# PENDIENTE DE VERIFICAR: igual que las llamaradas, estos datos se escribieron a mano; compáralos con las
# páginas de la NASA sobre Veggie y Plant Habitat-04 antes de la entrega.
PLANTS = {
    "lechuga": {
        "name": "Lechuga romana roja",
        "fact": "En agosto de 2015 la tripulación de la Estación Espacial comió lechuga romana roja cultivada "
                "en el sistema Veggie: fue la primera vez que astronautas de la NASA comieron algo cultivado en el espacio.",
    },
    "mizuna": {
        "name": "Mostaza mizuna",
        "fact": "La mostaza mizuna es una de las hojas verdes que los astronautas han cultivado en Veggie. "
                "Las plantas crecen con luces LED rojas, azules y verdes, porque en el espacio no hay luz de sol directa.",
    },
    "chile": {
        "name": "Chile Hatch",
        "fact": "En 2021 los astronautas cosecharon chiles en la Estación Espacial (experimento Plant Habitat-04). "
                "Tardaron unos 4 meses en crecer: uno de los experimentos de plantas más largos en órbita.",
    },
}

GREENHOUSE_SOURCES = "Fuente: NASA (Veggie, Plant Habitat-04) y NASA OSDR (osdr.nasa.gov). Datos guardados en el juego."

# Comunicaciones Tierra-Marte (fuente: NASA, Mars Exploration Program y Deep Space Network).
# PENDIENTE DE VERIFICAR, igual que los demás datos escritos a mano.
EARTH_MARS_MIN_KM = 54.6e6      # Distancia mínima aproximada entre la Tierra y Marte
EARTH_MARS_MAX_KM = 401e6       # Distancia máxima aproximada
LIGHT_SPEED_KM_S = 299_792.458  # Velocidad de la luz (y de las señales de radio)
COMMS_FACTS = [
    "La luz viaja a casi 300 mil kilómetros por segundo, pero Marte está tan lejos que un mensaje "
    "tarda entre 3 y 22 minutos en llegar, según dónde estén los dos planetas.",
    "La NASA habla con sus naves usando la Red de Espacio Profundo: antenas gigantes en California "
    "(Estados Unidos), Madrid (España) y Canberra (Australia).",
    "Más o menos cada 26 meses el Sol queda entre la Tierra y Marte, y durante unas dos semanas casi "
    "no se pueden enviar mensajes.",
    "Por el retraso de los mensajes, los astronautas en Marte tendrán que resolver muchos problemas "
    "sin esperar la respuesta de la Tierra.",
]
COMMS_SOURCES = "Fuente: NASA (Mars Exploration, Deep Space Network). Datos guardados en el juego."

DATA_SOURCES ="Fuente: NASA DONKI y misión Curiosity (RAD). Datos históricos guardados en el juego, no en tiempo real."


def flare_magnitude(flare_class):
    """ Convierte una clase de llamarada en un número comparable: X9.3 → 9.3, M5.0 → 0.5, C2.0 → 0.02 """
    scale = {"X": 1.0, "M": 0.1, "C": 0.01}
    return scale.get(flare_class[0], 0.01) * float(flare_class[1:])
