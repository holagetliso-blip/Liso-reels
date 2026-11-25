# liso-reels — Reels de prueba automáticos para @get.liso

Publica **Reels de prueba (trial reels)** en la cuenta de Instagram Business @get.liso desde un calendario en CSV, usando la **Instagram API with Instagram Login** (`graph.instagram.com`, v27.0). Después de 24 h trae los insights de cada reel y arma un ranking.

Solo Python 3 estándar. No hace falta instalar nada.

---

## 1. Qué hace cada archivo

| Archivo | Para qué |
|---|---|
| `calendario.csv` | El calendario. Vos cargás las filas; los scripts actualizan Estado, media_id e insights. |
| `check.py` | Verifica token, cuenta y cuota de publicación. **Correr primero.** |
| `publish.py` | Publica las filas `Pendiente` cuya fecha/hora ya pasó. `--dry-run` para ver sin publicar. |
| `report.py` | Trae insights (alcance, views, likes, comentarios, guardados, compartidos) y muestra ranking. |
| `refresh_token.py` | Renueva el token de 60 días y lo guarda en `.env`. |
| `common.py` | Código compartido. No hace falta tocarlo. |
| `launchagents/` | Los dos `.plist` para que la Mac corra todo sola. |
| `.github/workflows/publish.yml` | Alternativa con GitHub Actions (corre aunque la Mac duerma). |
| `logs/publish.log` | Log en español de todo lo que pasa. |

---

## 2. Configuración inicial (una sola vez)

### 2.1 Credenciales en `.env`

```bash
cp .env.example .env
open -e .env
```

Completá:

- `IG_ACCESS_TOKEN`: el token generado en el panel de Meta (ver 2.2).
- `IG_USER_ID`: el **ID de la cuenta de Instagram** que muestra el panel junto a @get.liso.
- `IG_APP_ID` y `IG_APP_SECRET`: Panel de la app → Configuración de la app → Básica. Hoy no se usan en los scripts; quedan guardados por si después hacés el login completo.

**Nunca** pegues el token en un chat ni lo subas a git (`.gitignore` ya excluye `.env`).

### 2.2 Conseguir el token y el ID en el panel de Meta

1. Entrá a [developers.facebook.com](https://developers.facebook.com) con la cuenta que creó la app → **Mis apps** → tu app.
2. Menú izquierdo → **Instagram** → **API setup with Instagram business login** (en español: "Configuración de la API con inicio de sesión de Instagram para empresas").
3. Paso **"Generar tokens de acceso"** → **Agregar cuenta** → iniciá sesión con **@get.liso**.
4. Si Instagram pide aceptar una invitación de tester: abrí la app de Instagram en el celular → Configuración → Sitio web y permisos → **Invitaciones de apps y sitios web** → Aceptar.
5. Al lado de @get.liso tocá **Generar token**. Marcá los permisos:
   - `instagram_business_basic`
   - `instagram_business_content_publish`
   - `instagram_business_manage_insights`
6. Copiá el token (es de larga duración, 60 días) y el **ID de la cuenta de Instagram** que aparece al lado. Pegalos en `.env`.

Si la pantalla cambió de nombre, buscá en el panel la sección de Instagram que diga "Instagram Login" / "Business Login for Instagram".

### 2.3 Los videos tienen que estar en una URL pública

Con Instagram Login, la API **descarga el video desde una URL**; no acepta archivos locales (la subida local solo existe para apps con Facebook Login). Entonces cada fila necesita `URL_video`.

La forma más simple para LISO: **Shopify → Contenido → Archivos → Subir archivo**. Shopify te da una URL del tipo `https://cdn.shopify.com/s/files/.../IMG_3668.mp4`. Esa es la que va en el CSV. Alternativas: Dropbox (link con `?dl=1`), Google Drive público, Cloudflare R2.

Requisitos del video para Reels: MP4 o MOV, vertical 9:16 recomendado, 3 s a 15 min, hasta 1 GB. Los `.MOV` de iPhone funcionan, pero conviene convertirlos a MP4 (H.264) para evitar rechazos.

---

## 3. Cómo se usa

### 3.1 El calendario

Abrí `calendario.csv` (Numbers, Excel o Google Sheets; guardalo siempre como **CSV UTF-8**). Columnas que cargás vos:

| Columna | Ejemplo |
|---|---|
| `Fecha` | `2026-11-26` |
| `Hora` | `11:30` (hora de Buenos Aires) |
| `Archivo` | `IMG_3668.MP4` |
| `Creadora` | `Juanita` |
| `Qué muestra` | `Unboxing + uso en el auto` |
| `Descripción` | el texto del reel |
| `Hashtags` | `#liso #alisadoraportatil` |
| `Estado` | `Pendiente` para publicar. `Reserva` = todavía no. |
| `Notas` | lo que quieras; los scripts escriben acá si hay error |
| `URL_video` | la URL pública del video |

Las demás columnas (`container_id`, `media_id`, `Publicado_en`, `reach`, `views`, …) las escriben los scripts. No las edites a mano.

Estados posibles: `Pendiente` → `Publicado` | `Error`. `Reserva` se ignora.

### 3.2 Orden de la primera vez

```bash
cd ~/Desktop/liso-reels
python3 check.py                      # 1. token, cuenta y cuota
python3 publish.py --dry-run          # 2. qué publicaría, sin tocar la API
python3 publish.py --only IMG_3668.MP4 --ignore-time   # 3. UN reel real
```

Para el paso 3 la fila tiene que tener `Estado=Pendiente` y `URL_video` cargada. `--ignore-time` publica aunque la fecha/hora no haya llegado.

Después revisá en Instagram (perfil → pestaña Reels → el reel tiene la etiqueta "Prueba") y, si está bien, recién ahí activá la automatización (sección 4).

### 3.3 Reglas que aplica `publish.py`

- Publica una fila si está `Pendiente` y su fecha/hora ya pasó o falta menos de 10 minutos.
- Nunca publica dos reels con menos de 5 minutos entre sí.
- Estrategia de graduación por defecto **`SS_PERFORMANCE`**: Instagram lo comparte solo con todos tus seguidores si rinde bien entre no-seguidores. Con `--strategy MANUAL` lo graduás vos desde la app.
- No manda `share_to_feed` (un reel de prueba no va al feed hasta que gradúa). Si alguna vez hace falta, cambiá `SHARE_TO_FEED` en `publish.py`.
- Si Instagram responde que llegaste al **máximo de reels de prueba** del día, frena, lo anota en `Notas` y sigue mañana.
- Si una fila falla, queda en `Error` con el mensaje en `Notas` y sigue con las demás.

### 3.4 Reporte

```bash
python3 report.py          # insights de los reels con más de 24 h
python3 report.py --all    # reconsulta todos
```

Imprime un ranking por alcance y guarda los números en el CSV.

### 3.5 Renovar el token (¡antes de los 60 días!)

El token vence a los 60 días. `refresh_token.py` lo renueva y guarda la fecha estimada de vencimiento en `.env` (`IG_TOKEN_VENCE`). El token tiene que tener más de 24 h para poder renovarse.

```bash
python3 refresh_token.py
```

**Agendalo el día 1 de cada mes.** Si se vence, hay que generar uno nuevo en el panel (sección 2.2).

---

## 4. Automatización en la Mac (LaunchAgents)

Dos tareas: `publish.py` cada 10 minutos y `report.py` todos los días a las 9:00.

### Cargar

```bash
cd ~/Desktop/liso-reels
cp launchagents/com.liso.reels.publish.plist ~/Library/LaunchAgents/
cp launchagents/com.liso.reels.report.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.liso.reels.publish.plist
launchctl load ~/Library/LaunchAgents/com.liso.reels.report.plist
launchctl list | grep liso        # tiene que mostrar las dos
```

### Descargar (pausar todo)

```bash
launchctl unload ~/Library/LaunchAgents/com.liso.reels.publish.plist
launchctl unload ~/Library/LaunchAgents/com.liso.reels.report.plist
```

### Importante

- Los `.plist` apuntan a `/Users/bautidelrio/Desktop/liso-reels`. Si movés la carpeta o es otro usuario, editá las rutas en los dos archivos.
- **Si la Mac está dormida o apagada, no corre nada.** Las filas que vencieron se publican en la primera corrida cuando se despierte. Para evitarlo: Configuración → Batería → Impedir reposo automático con el adaptador conectado, o usá la alternativa de abajo.
- Si al cargar aparece "Operation not permitted" o la tarea no corre, dale acceso a Python en Configuración → Privacidad y seguridad → Acceso total al disco (agregá `/usr/bin/python3`).
- La salida de launchd queda en `logs/launchd.*.out` y `.err`; lo importante está en `logs/publish.log`.

---

## 5. Alternativa: GitHub Actions (corre aunque la Mac duerma)

Ya está armado en `.github/workflows/publish.yml`.

1. Creá un repo **privado** en GitHub y subí la carpeta (sin `.env`, el `.gitignore` ya lo excluye).
2. Repo → Settings → Secrets and variables → Actions → **New repository secret**: `IG_ACCESS_TOKEN` e `IG_USER_ID`.
3. Settings → Actions → General → Workflow permissions → **Read and write** (para que pueda guardar el CSV actualizado).
4. Listo: corre cada 10 minutos y el reporte a las 9:00 de Buenos Aires. El calendario actualizado se commitea solo; para cargar filas nuevas editás el CSV y hacés push (o lo editás desde la web de GitHub).

Ojo: cuando renueves el token con `refresh_token.py`, actualizá también el secret en GitHub. Y los cron de GitHub pueden demorar algunos minutos; no son al segundo.

Si usás GitHub Actions, **descargá los LaunchAgents** para no publicar dos veces.

---

## 6. Errores comunes

| Mensaje | Qué es | Qué hacer |
|---|---|---|
| `code=190` | Token vencido o inválido | Generar token nuevo en el panel y pegarlo en `.env` |
| `IG_USER_ID NO coincide` | El ID de `.env` no es el de la cuenta del token | Copiar el ID que muestra el panel al lado de @get.liso |
| `permission` / `code=10` | Falta `instagram_business_content_publish` | Regenerar el token marcando los 3 permisos |
| `Media download failed` / `code=9004` | La URL del video no es pública o no es un video válido | Probar la URL en una ventana de incógnito; convertir a MP4 |
| `The user is not an Instagram Business` | La cuenta no es profesional | Instagram → Configuración → Tipo de cuenta → Empresa |
| `maximum number of trial reels` | Límite diario de reels de prueba | Esperar a mañana; el script ya frenó solo |
| `Contenedor en estado ERROR` | Instagram rechazó el video | Ver `status` en Notas; suele ser formato o duración |
