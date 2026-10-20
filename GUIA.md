# Puesta en marcha (≈15 minutos, todo gratis)

## 1. Crea el bot de Telegram
1. En Telegram abre **@BotFather** → escribe `/newbot` → elige nombre y usuario.
2. Te dará un **token** (algo como `123456:ABC...`). Guárdalo.
3. Abre tu bot nuevo y pulsa **Iniciar** (o escríbele "hola").
4. En el navegador abre `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` (sustituye `<TU_TOKEN>`).
   Busca `"chat":{"id":` → ese número es tu **chat id**.

## 2. Crea la cuenta y el repositorio en GitHub
1. Regístrate en github.com (gratis).
2. **New repository** → nombre p. ej. `todoterrenos` → **Public** → Create.
   (Público es necesario para alojar la app gratis. Solo serán públicos los anuncios, no tu token.)

## 3. Sube los archivos
1. En el repo: **Add file → Upload files** y arrastra TODO el contenido de esta carpeta
   (`index.html`, `scraper.py`, `sw.js`, `manifest.json`, los dos `icon-*.png` y la carpeta `data`). **Commit changes**.
2. El workflow va aparte (carpeta oculta): **Add file → Create new file**, en el nombre escribe
   `.github/workflows/buscar.yml` (las `/` crean las carpetas), pega el contenido del archivo `buscar.yml` y **Commit**.

## 4. Configura GitHub
1. **Settings → Secrets and variables → Actions → New repository secret**:
   crea `TG_TOKEN` (el token) y `TG_CHAT` (el chat id).
2. **Settings → Actions → General → Workflow permissions → Read and write permissions** → Save.
3. **Settings → Pages → Build and deployment**: Source = *Deploy from a branch*, Branch = `main` / `(root)` → Save.

## 5. Primer rastreo
1. Pestaña **Actions → Buscar anuncios → Run workflow**. Tarda 1-2 min.
2. Recibirás en Telegram un resumen y los 5 anuncios más cercanos.
3. Tu app estará en `https://TU_USUARIO.github.io/todoterrenos/`. Ábrela en el móvil y usa
   **Añadir a pantalla de inicio** (Chrome: menú ⋮ → Instalar app).

## Ajustes
Edita `scraper.py` (arriba del todo): precio, km máximos, modelos, origen.

## Límites a tener en cuenta
- Ahora rastrea **Wallapop**. Milanuncios, Coches.net, etc. bloquean a los robots desde servidores en la nube; hay que probarlos uno a uno antes de añadirlos.
- Wallapop no tiene API pública: si cambia algo, el rastreo puede fallar (se verá en la pestaña Actions).
- Tus marcas "Me interesa / Descartar" se guardan en el móvil donde las haces (no se sincronizan entre dispositivos).
- GitHub puede retrasar los avisos programados unos minutos y pausa los workflows si el repo lleva 60 días sin actividad: bastaría pulsar *Enable* en Actions.
