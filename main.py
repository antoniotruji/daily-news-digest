import feedparser
import calendar
from datetime import datetime, timezone, timedelta
import smtplib
from email.message import EmailMessage

from google.genai import errors as genai_errors

import random, time

import logging
logging.getLogger("google_genai").setLevel(logging.ERROR)

import re

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

# Feeds de origen: (nombre_legible, url)
FEEDS = [
    ("Financial Times", "https://www.ft.com/rss/home"),
    ("El Confidencial", "https://rss.elconfidencial.com/espana/"),
]

# Ventana de tiempo: solo noticias de las últimas 24 horas
VENTANA_HORAS = 24


def obtener_noticias():
    limite = datetime.now(timezone.utc) - timedelta(hours=VENTANA_HORAS)
    noticias = []

    for fuente, url in FEEDS:
        feed = feedparser.parse(url)
        print(f"[{fuente}] {len(feed.entries)} entradas encontradas en el feed")

        for entrada in feed.entries:
            # feedparser normaliza la fecha en 'published_parsed' (struct_time en UTC)
            fecha_struct = entrada.get("published_parsed")
            if not fecha_struct:
                continue  # sin fecha fiable, la descartamos

            fecha = datetime.fromtimestamp(calendar.timegm(fecha_struct), tz=timezone.utc)
            if fecha < limite:
                continue  # más antigua de 24h, la descartamos

            noticias.append({
                "fuente": fuente,
                "titular": entrada.get("title", "").strip(),
                "descripcion": entrada.get("summary", "").strip(),
                "fecha": fecha.isoformat(),
            })

    return noticias

MODELOS = ["gemini-3.6-flash", "gemini-flash-latest"]

INSTRUCCIONES = """Eres mi asistente financiero y de actualidad diario. A partir de la lista de
noticias en bruto que te paso, genera un briefing con DOS secciones. Todo en español.

=== SECCIÓN 1: LO IMPORTANTE DE HOY ===
- NO diferencies por periódico ni por temática. Quiero un único resumen fluido de lo que
  de verdad importa hoy en el mundo y en España.
- Básate SOBRE TODO en las noticias del Financial Times (contexto mundial). De El Confidencial,
  escoge SOLO las 5 más importantes (contexto España) e intégralas.
- Selecciona lo relevante: tecnología, política, economía, geopolítica y sucesos graves.
  Descarta lo trivial, deportes, cultura y estilo de vida.
- El Financial Times viene en inglés: tradúcelo. El Confidencial ya está en español.
- Escribe entre 5 y 8 puntos, cada uno de 2-3 líneas, en orden de importancia.

=== SECCIÓN 2: ANÁLISIS DE MERCADO E IDEAS DE INVERSIÓN ===
- Analiza cómo está el mercado HOY, anclándote en las noticias de la Sección 1
  (tipos de interés, inflación, geopolítica, tecnología, energía, resultados empresariales...).
- Da un párrafo breve de contexto: ¿qué sensación hay en los mercados y por qué?
- Luego, en formato claro, indica:
  · DÓNDE podría tener sentido invertir ahora y POR QUÉ (sectores, tipos de activo, regiones).
  · DÓNDE conviene ser cauto o evitar ahora y POR QUÉ.
- Explica SIEMPRE el razonamiento detrás de cada idea, con lógica económica sencilla,
  como para alguien que está aprendiendo a invertir.
- Sé equilibrado: menciona también el riesgo o el otro punto de vista de cada idea.
- Termina explicando aquellos conceptos que sean un poco más complejos de entender para alguien que no sepa mucho de economía o finanzas.

FORMATO DE SALIDA:
- Devuelve SOLO fragmento HTML, sin ```html ni <html> ni <body>.
- La frase del principio va en un <p> con <em>.
- Usa <h2> para el título de cada sección y <p> o <ul><li> para el contenido.
- Resalta lo importante con <strong>. No añadas estilos CSS.
"""


def construir_prompt(noticias):
    lineas = []
    for n in noticias:
        lineas.append(
            f"- Fuente: {n['fuente']} | Titular: {n['titular']} | Descripción: {n['descripcion']}"
        )
    return INSTRUCCIONES + "\n\nNOTICIAS EN BRUTO:\n" + "\n".join(lineas)

def _llamar_modelo(client, modelo, prompt, intentos=4):
    for intento in range(1, intentos + 1):
        try:
            respuesta = client.models.generate_content(model=modelo, contents=prompt)
            texto = respuesta.text.strip()
            return texto.removeprefix("```html").removeprefix("```").removesuffix("```").strip()
        except genai_errors.ServerError:
            if intento == intentos:
                raise  # agotados los reintentos de este modelo; salta al siguiente
            espera = min(60, 5 * 2 ** (intento - 1)) + random.uniform(0, 3)
            print(f"[{modelo}] saturado (503). Reintento {intento}/{intentos} en {espera:.0f}s...")
            time.sleep(espera)
            
def resumir_con_ia(noticias):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    prompt = construir_prompt(noticias)

    for modelo in MODELOS:
        return _llamar_modelo(client, modelo, prompt)

    raise RuntimeError("Todos los modelos están saturados.")

def enviar_email(cuerpo_ia):
    remitente = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_APP_PASSWORD")
    destinatarios = [e.strip() for e in os.getenv("EMAIL_TO", "").split(",") if e.strip()]

    if not destinatarios:
        print("No hay destinatarios configurados en EMAIL_TO.")
        return

    html_completo = construir_html(cuerpo_ia)

    msg = EmailMessage()
    msg["Subject"] = f"Tu hombre te informa — {datetime.now().strftime('%d/%m/%Y')}"
    msg["From"] = remitente
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(html_a_texto(html_completo))       # versión texto (fallback)
    msg.add_alternative(html_completo, subtype="html")  # versión HTML (la que se ve)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
        servidor.login(remitente, password)
        servidor.send_message(msg)

    print(f"Correo enviado correctamente a: {', '.join(destinatarios)}")

def construir_html(cuerpo_ia):
    fecha = datetime.now().strftime("%d/%m/%Y")
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;">
  <div style="max-width:640px;margin:0 auto;padding:24px;">
    <div style="background:#ffffff;border-radius:10px;padding:28px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
      <h1 style="margin:0 0 4px;font-size:22px;color:#0b3d91;">📰 Resumen de noticias</h1>
      <p style="margin:0 0 20px;color:#666;font-size:13px;">{fecha}</p>
      {cuerpo_ia}
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0 12px;">
      <p style="color:#999;font-size:11px;margin:0;">Generado automáticamente · Financial Times &amp; El Confidencial</p>
    </div>
  </div>
</body>
</html>"""


def html_a_texto(html):
    # Versión en texto plano para clientes que no muestran HTML
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"<[^>]+>", "", html)).strip()

if __name__ == "__main__":
    noticias = obtener_noticias()
    print(f"\n=== {len(noticias)} noticias recopiladas ===\n")

    if not noticias:
        print("No hay noticias recientes. Nada que enviar.")
    else:
        resumen = resumir_con_ia(noticias)
        enviar_email(resumen)
