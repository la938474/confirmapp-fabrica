# Fábrica de videos Confirmapp 🏭

Arma Reels de Confirmapp todos los días y los deja en la rama `cola`.
Supabase los importa cada hora y los publica en Instagram y Facebook a las 9:00, 14:00 y 20:00 (hora de México).

- `INSTRUCCIONES.md` — la receta diaria (reglas, formatos, escenas, pasos).
- `fabrica.py` — `hacer guiones/AAAA-MM-DD.json` y `publicar`.
- `guiones/` — los guiones de cada día. `historial.json` — todo lo que ya se hizo.
- `assets/` — capturas por giro, plantilla de cuadros, música. `tts/` — voz (Kokoro, partida en pedazos).
