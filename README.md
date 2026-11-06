# daily-news-digest
Resumen diario de noticias (Financial Times y El Confidencial) generado con IA y enviado por email automáticamente.

Script en Python que cada mañana recopila noticias de **Financial Times** y
**El Confidencial** vía RSS, genera un resumen con **IA (Google Gemini)** y lo
envía por **email**. Pensado para ejecutarse de forma autónoma en un servidor
Linux mediante un *timer* de systemd.

## Qué hace

- Descarga los feeds RSS y filtra las noticias de las últimas 24 h.
- Envía los titulares a Gemini, que redacta un briefing en español con:
  - un resumen de lo más importante del día (mundo y España),
  - un análisis de mercado con ideas de inversión y su razonamiento.
- Formatea el resultado en HTML y lo manda por correo (SMTP de Gmail).

## Stack

Python 3 · feedparser · google-genai · smtplib · systemd

## Instalación

```bash
git clone https://github.com/TU_USUARIO/news-digest-ia.git
cd news-digest-ia
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuración

Copia la plantilla y rellena tus credenciales:

```bash
cp .env.example .env
```

| Variable | Descripción |
|---|---|
| `GEMINI_API_KEY` | API key de Google AI Studio |
| `GMAIL_USER` | Cuenta de Gmail que envía |
| `GMAIL_APP_PASSWORD` | Contraseña de aplicación de Gmail (requiere 2FA) |
| `EMAIL_TO` | Destinatarios, separados por comas |

> El archivo `.env` está excluido en `.gitignore`: nunca subas tus credenciales.

## Uso

Manual:

```bash
python main.py
```

Automático (ejecución diaria): configurar un `news.service` + `news.timer`
de systemd que lance el script a la hora deseada.

## Aviso

El análisis de inversión es contenido educativo generado por IA, no
asesoramiento financiero.
