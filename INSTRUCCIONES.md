# Fábrica de videos Confirmapp — receta diaria

Este repositorio arma videos verticales (Reels) para promocionar **Confirmapp** y los deja en la rama `cola`.
Supabase revisa la cola cada hora, guarda los videos y los publica solo en Instagram (@confirmapp.mx) y
Facebook (página Confirmapp) a las **9:00, 14:00 y 20:00** (hora de México), uno detrás de otro.

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
- `texto` (caption): termina con "Pruébalo 7 días gratis 👉 confirmapp.com.mx" y hashtags del giro + `#confirmapp`.

## Pasos de cada día
1. `git pull` en `main`.
2. Leer el resumen de Supabase (la liga viene en las instrucciones de la tarea programada) y `historial.json`.
   - Si `pendientes_por_publicar` es **9 o más**: no hagas videos hoy (ya hay 3 días en fila).
   - Si no: haz **3 videos**.
3. Elegir giros: alternar; dar más turnos a los giros/ganchos/formatos con más vistas y compartidos en el resumen
   (cuando ya haya datos). Nunca repetir un `gancho` del historial. Dentistas, médicos, psicólogos y salones son
   los giros principales: que al menos 1 de los 3 sea de ellos.
4. Escribir `guiones/AAAA-MM-DD.json` y correr `python3 fabrica.py hacer guiones/AAAA-MM-DD.json`
   (si marca errores, corregir el guion y repetir).
5. Revisar al menos una imagen de cada video en `trabajo/<id>/img/` (que el texto no se salga ni se encime).
6. `python3 fabrica.py publicar` (sube a `cola`, guarda historial y guion en `main`).
7. Los **lunes**: mandar a Luis un resumen corto en español: top 3 videos de la semana (vistas, compartidos),
   qué estilo pegó más, cuántos videos hay en fila y cualquier error de publicación.
