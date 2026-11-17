# Fábrica de videos Confirmapp — receta diaria

Este repositorio arma videos verticales (Reels) para promocionar **Confirmapp** y los deja en la rama `cola`.
Supabase revisa la cola cada hora, guarda los videos y los publica solo en Instagram (@confirmapp.mx) y
Facebook (página Confirmapp) a las **9:00, 14:00 y 20:00** (hora de México), uno detrás de otro.
Cada video en `cola.json` trae `portada` (jpg de la primera escena, para usarla como portada del Reel) y
`historia: true` (también se sube a Historias). La primera escena no lleva fundido a negro: su primer cuadro es la portada.

## Qué es Confirmapp (lo único que se puede decir)
- Confirma citas por **WhatsApp un día antes**; el cliente confirma o cancela con un toque.
- En el calendario se ve quién viene: ✅ confirmó · 🟡 esperando · ❎ canceló.
- **Autoagenda**: un link para que los clientes elijan su horario libre; al negocio le llega un WhatsApp con quién agendó.
- **Magic**: escribes la cita con el dedo (como en agenda de papel) y se agenda sola.
- **ConfirChat IA**: contesta el WhatsApp del negocio y agenda citas 24/7.
- Funciona con **Google Calendar u Outlook**. **7 días gratis, sin tarjeta**, en confirmapp.com.mx.
- Planes desde **$149 al mes** (México). Funciona en varios países de Latinoamérica.
- Si invitas a un colega con tu código, ganan 7 días más los dos.
- Giros: ver `assets/giros.json`.

## Reglas (no romper)
- Español de México, cercano, directo. Nada de groserías ni de burlarse de los clientes del negocio.
- **No inventar** estadísticas, porcentajes, testimonios, reseñas, nombres de clientes reales, premios ni funciones.
  Se vale hablar de situaciones comunes ("¿otro paciente que no llegó?") sin cifras.
- No mencionar otras marcas ni competidores. No prometer resultados ("vas a ganar el doble").
- Precio: solo "desde $149 al mes" o "7 días gratis".
- **Pronunciación** (el campo `v` es lo que dice la voz): escribe "Confirm ap" (no Confirmapp), "guatsap" (WhatsApp),
  "Gúgol" (Google), "Áutluk" (Outlook), "Máyic" (Magic), "Confirchat i a" (ConfirChat IA),
  "confirm ap punto com punto eme equis" (la página). Números y horas con letra ("siete días", "las once de la noche").
  Sin emojis en `v`.
- En `t` (título en pantalla) se vale `<mark>palabra</mark>` para resaltar 1–3 palabras. Títulos cortos (máx. ~45 letras).

## Escenas disponibles (`img`)
| img | Qué se ve | Usa `t` / `s` / `e` |
|---|---|---|
| `HOOK` | Emoji gigante + título + subtítulo centrados | `e` emoji, `t`, `s` |
| `FRASE` | Frase grande a la izquierda (estilo "POV") | `t`, `s` opcional |
| `LISTA` | Título + 2 a 4 puntos numerados | `t`, `s` = puntos separados por `\|` |
| `k_gcal` | Calendario con citas confirmadas/canceladas | `t`, `s` |
| `k_chat` | ConfirChat IA agendando en WhatsApp | `t`, `s` |
| `k_magic` | Magic: cita escrita a mano | `t`, `s` |
| `m_pAutoMenu` | Link de Autoagenda | `t`, `s` |
| `m_pSusc` | Planes / invita a un colega | `t`, `s` |
| `01_login` … `05_google` | Pasos para empezar (entrar, elegir giro, datos, prueba, conectar calendario) | `t`, `s`, `n` (etiqueta tipo "PASO 1") |
| `CTA` | Cierre: 7 días GRATIS + confirmapp.com.mx | `s` opcional; **siempre la última** |

Las capturas cambian solas según el giro (nombres y servicios del giro).

## Formatos (rotar, no repetir el mismo dos veces seguidas)
1. **problema** — pregunta que duele → cómo lo resuelve → CTA.
2. **lista** — "3 señales / 3 errores / 3 cosas" (LISTA) → solución → CTA.
3. **pov** — FRASE tipo "POV: tus pacientes confirman solos y tú…" → 1–2 capturas → CTA.
4. **tutorial** — "Así empiezas en 1 minuto" con 2–3 pasos (`01_login`, `02_giro`, `05_google`) → CTA.
5. **antes-despues** — FRASE "Antes: …" → FRASE "Ahora: …" → captura → CTA.
6. **funcion** — una sola función a fondo (Magic, ConfirChat IA o Autoagenda) → CTA.
7. **pregunta** — pregunta frecuente ("¿Y si mi paciente no tiene guatsap?" NO; solo preguntas que se puedan contestar con la info de arriba).

Duración ideal: 15–30 s (3 a 5 escenas). La primera escena es el gancho: corto, que detenga el dedo.

## Formato del guion (`guiones/AAAA-MM-DD.json`)
```json
[
 {"id": "2026-11-16-psico-lista", "giro": "psicologia", "formato": "lista", "voz": "dora_brillante", "velocidad": 1.12,
  "gancho": "3 señales de que pierdes sesiones",
  "texto": "Caption para IG/FB con 1–2 líneas + CTA + 4–6 hashtags",
  "escenas": [
   {"img": "FRASE", "t": "3 señales de que <mark>pierdes sesiones</mark>", "v": "Tres señales de que estás perdiendo sesiones."},
   {"img": "LISTA", "t": "¿Te pasa?", "s": "Huecos en tu agenda|Pacientes que \"se olvidaron\"|Confirmas a mano", "v": "..."},
   {"img": "k_gcal", "t": "Que confirmen <mark>solos</mark> ✅", "s": "WhatsApp automático un día antes", "v": "..."},
   {"img": "CTA", "v": "Pruébalo siete días gratis, en confirm ap punto com punto eme equis."}
  ]}
]
```
- `id`: fecha + giro + formato (minúsculas, sin acentos, único).
- `voz`: `dora_brillante` (mujer) o `alex_grave` (hombre). Alternar.
- `texto` (caption): antes de los hashtags incluye la línea "💬 Comenta PRUEBA y te mando el video y el link por mensaje 📩" (la máquina de redes contesta sola por mensaje privado), luego "Pruébalo 7 días gratis 👉 confirmapp.com.mx" y hashtags del giro + `#confirmapp`.

## Pasos de cada día
1. `git pull` en `main`.
2. Leer `resumen.json` (lo guarda GitHub cada hora desde Supabase; `leido` dice cuándo) y `historial.json`.
   Si `resumen.json` no existe o tiene más de 6 horas, se toma como "no se pudo leer".
   - Si `pendientes_por_publicar` es **9 o más**: no hagas videos hoy (ya hay 3 días en fila).
   - Si no: haz **3 videos**.
3. Elegir giros: alternar; dar más turnos a los giros/ganchos/formatos con más vistas y compartidos en el resumen
   (cuando ya haya datos). Nunca repetir un `gancho` del historial. Dentistas, médicos, psicólogos y salones son
   los giros principales: que al menos 1 de los 3 sea de ellos.
4. Escribir `guiones/AAAA-MM-DD.json` y correr `python3 fabrica.py hacer guiones/AAAA-MM-DD.json`
   (si marca errores, corregir el guion y repetir).
5. Revisar al menos una imagen de cada video en `trabajo/<id>/img/` (que el texto no se salga ni se encime).
5b. `python3 fabrica.py avatares` (videos de avatar IA que Luis sube a `avatar/`; se corre **todos los días**,
    aunque hoy no toque hacer videos).
6. `python3 fabrica.py publicar` (sube a `cola`, guarda historial y guion en `main`).
7. Los **lunes**: mandar a Luis un resumen corto en español: top 3 videos de la semana (vistas, compartidos),
   qué estilo pegó más, cuántos videos hay en fila y cualquier error de publicación.

## Videos con avatar IA (HeyGen a mano + todo lo demás automático)
Luis prefiere la calidad de HeyGen (plan gratis, a mano). El flujo:
1. Cada lunes GitHub (`avatar-ia.yml` → `avatar_ia.py --kit`) prepara en `kit-heygen/<num>-<personaje>/` la foto
   (Cloudflare, solo si el personaje no existe), la voz `voz.mp3` (Kokoro) y un `LEEME.txt`.
2. Luis hace el video en HeyGen con esa foto y ese audio, y lo sube a `avatar/<num>.mp4`.
3. La fábrica (`python3 fabrica.py avatares`) le pone celular con capturas reales, leyenda IA, portada y caption,
   lo manda a la fila y borra su kit.
SadTalker (gratis pero de menor calidad) quedó apagado; solo si Luis lo pide.
**Estilo "grande" (el que le gusta a Luis):** en `pendientes.json` pon `"estilo": "grande"` y `"cara": [cx, cy, r]`
(centro y radio de la cara en el cuadro 1080x1920). En el gancho se ve el avatar completo; en las explicaciones el celular
ocupa casi toda la pantalla y la cara habla en un círculo arriba. En `capturas` se puede usar `"img"` (captura fija) o
`"anim"` (animación de la app en `assets/anim/`): `autoagenda` (mandas el link → la clienta escoge horario → te llega el
WhatsApp; `q.p1`/`q.p2` = segundos dentro del tramo en que cambia de pantalla) y `recordatorio` (WhatsApp de recordatorio →
toca Confirmar → en el calendario pasa de 🟡 a ✅). El cierre siempre con `01_login` (prueba gratis 7 días).
**Sincronía celular ↔ voz (importante):** lo que sale en el celular debe corresponder a lo que dice en ese momento.
Antes de `avatares`, para cada `avatar/<num>.mp4` (salvo si su guion trae `"capturas_revisadas": true`, que ya ajustó Claude con Luis; ese no lo toques) compara su duración con la suma de su `voz.mp3`. Si difiere más de 0.5 s
(Luis escribió el texto en HeyGen en vez de subir el audio), detecta las pausas con
`ffmpeg -i avatar/<num>.mp4 -af silencedetect=n=-35dB:d=0.25 -f null -`, empata cada tramo hablado con las frases del guion
(por número de sílabas) y reescribe `capturas` en `pendientes.json` con los segundos reales. Cada captura debe mostrar
exactamente lo que se menciona (Autoagenda → m_pAutoMenu, WhatsApp/cita agendada → k_chat, recordatorio un día antes → 04_prueba,
quién viene/calendario → k_gcal, 7 días gratis/CTA → 01_login, Magic → k_magic, planes/invitar → m_pSusc). En el gancho no pongas celular.

Reglas de contenido:
- El avatar **demuestra** la app ("mira", "te enseño", "así se ve"). Nunca dice que es cliente real, ni nombra un negocio,
  ni promete resultados, ni da cifras. Caption siempre con "🤖 Escena recreada con IA".

Si quedan menos de 3 guiones en `pendientes.json`, escribe 4 nuevos (rota dental, médico, psicología, salón y a veces otros giros)
y agrégalos a `pendientes.json` con números nuevos (mayores que cualquiera usado) y estos campos:
```json
{"num": 5, "id": "avatar-dental-xxxx", "giro": "dental", "gancho": "...", "texto": "caption ... 🤖 Escena recreada con IA\n#hashtags #confirmapp",
 "personaje": "recepcionista_dental", "voz": "dora_brillante",
 "foto_prompt": "Mexican woman, 32 years old, dental receptionist in light blue scrubs, dental clinic reception",
 "frases": ["gancho (1 frase)", "cómo funciona", "detalle", "Pruébalo siete días gratis, en confirm ap punto com punto eme equis."],
 "capturas_frase": [{"img": "k_gcal", "frase": 1, "hasta_frase": 3}]}
```
- `frases`: 3 a 5, total 15–25 s, con la pronunciación de arriba (Confirm ap, guatsap, Gúgol…). La última siempre es el CTA.
- `personaje`: reutiliza los de `avatar-ia/personajes/` (medico, recepcionista_dental, estilista, psicologa) para que la cara
  sea la misma; inventa uno nuevo solo si hace falta (con `foto_prompt`). `voz`: `dora_brillante` mujer, `alex_grave` hombre.
- `capturas_frase`: qué captura real sale en el celular y en qué frases (índices de `frases`). Solo capturas que existan en
  `assets/giros/<giro>/` (01_login … 05_google, k_chat, k_gcal, k_magic, m_pAutoMenu, m_pSusc).
- Nunca repitas un `gancho` del historial.
