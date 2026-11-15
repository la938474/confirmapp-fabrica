"""Avatares IA 100% automáticos y gratis (corre en GitHub Actions).

Para cada guion de guiones-avatar/pendientes.json que todavía no tenga video en avatar/:
  1. Foto del personaje: avatar-ia/personajes/<personaje>.jpg. Si no existe, la genera con
     Cloudflare Workers AI (FLUX, capa gratis) usando "foto_prompt". Necesita CF_ACCOUNT_ID y CF_API_TOKEN.
  2. Voz: Kokoro (la misma de los Reels) con las "frases" del guion.
  3. Video: SadTalker (código abierto, en CPU) hace hablar a la foto.
  4. Lo deja en avatar/<num>.mp4. La fábrica diaria le pone las capturas de la app, la leyenda de IA,
     portada y caption, y lo manda a la fila.

  python3 avatar_ia.py [--max 2] [--num 4] [--salida carpeta]
"""
import argparse, base64, json, os, subprocess, sys, urllib.request

R = os.path.dirname(os.path.abspath(__file__))
ST = os.environ.get('SADTALKER', f'{R}/../SadTalker')
PY_ST = os.environ.get('SADTALKER_PY', sys.executable)
NEG = (', looking directly at camera, mouth closed, gentle smile, face centered and well lit, only one person, '
       'softly blurred background, no text, no signs, no logos, upper body, vertical portrait, realistic photo')


def sh(*a, **k):
    subprocess.run(a, check=True, **k)


def foto(g, ruta):
    """Genera la foto con Cloudflare Workers AI (FLUX schnell) y la recorta a vertical 720x1280."""
    cuenta, token = os.environ.get('CF_ACCOUNT_ID'), os.environ.get('CF_API_TOKEN')
    if not (cuenta and token):
        sys.exit(f'Falta la foto {ruta} y no hay CF_ACCOUNT_ID/CF_API_TOKEN para generarla.')
    url = f'https://api.cloudflare.com/client/v4/accounts/{cuenta}/ai/run/@cf/black-forest-labs/flux-1-schnell'
    cuerpo = json.dumps({'prompt': g['foto_prompt'] + NEG, 'steps': 8}).encode()
    req = urllib.request.Request(url, cuerpo, {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    res = json.load(urllib.request.urlopen(req, timeout=180))
    if not res.get('success'): sys.exit(f'Cloudflare no generó la foto: {res.get("errors")}')
    tmp = ruta + '.tmp.jpg'
    open(tmp, 'wb').write(base64.b64decode(res['result']['image']))
    from PIL import Image
    im = Image.open(tmp).convert('RGB'); w, h = im.size
    cw = min(w, round(h * 9 / 16)); x = (w - cw) // 2
    im.crop((x, 0, x + cw, h)).resize((720, 1280), Image.LANCZOS).save(ruta, quality=95)
    os.remove(tmp)
    print('  foto generada:', ruta, flush=True)


def voz(g, ruta):
    sys.path.insert(0, f'{R}/tts'); sys.path.insert(0, R)
    import kok, fabrica
    partes = []
    for i, t in enumerate(g['frases']):
        raw = f'{ruta}.{i}.raw.wav'; f = f'{ruta}.{i}.wav'
        kok.guardar(kok.decir(t, g.get('voz', 'dora_brillante'), float(g.get('velocidad', 1.08))), raw)
        sh('ffmpeg', '-y', '-v', 'error', '-i', raw, '-af', fabrica.FILTRO_VOZ + ',apad=pad_dur=0.35', '-ar', '16000', '-ac', '1', f)
        partes.append(f)
    lst = ruta + '.txt'; open(lst, 'w').write('\n'.join(f"file '{p}'" for p in partes))
    sh('ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, ruta)
    # segundos donde empieza cada frase (para poner las capturas en su lugar)
    t, marcas = 0.0, []
    for p in partes:
        marcas.append(round(t, 2)); t += float(subprocess.check_output(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]))
    return marcas, round(t, 2)


def video(img, wav, salida, tmp):
    os.makedirs(tmp, exist_ok=True)
    sh(PY_ST, 'inference.py', '--driven_audio', wav, '--source_image', img, '--result_dir', tmp,
       '--still', '--preprocess', 'full', '--enhancer', 'gfpgan', '--cpu', '--batch_size', '4', cwd=ST)
    mp4 = sorted((os.path.join(dp, f) for dp, _, fs in os.walk(tmp) for f in fs if f.endswith('.mp4')), key=os.path.getmtime)[-1]
    # SadTalker devuelve audio en 16 kHz; lo volvemos a pegar en buena calidad
    sh('ffmpeg', '-y', '-v', 'error', '-i', mp4, '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p',
       '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-movflags', '+faststart', salida)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=2); ap.add_argument('--num', type=int)
    ap.add_argument('--salida', default=f'{R}/avatar')
    a = ap.parse_args()
    P = f'{R}/guiones-avatar/pendientes.json'
    pend = json.load(open(P))
    hechos = {int(f.split('.')[0].split(' ')[0]) for f in os.listdir(f'{R}/avatar') if f[:1].isdigit()}
    cola = [g for g in pend if g.get('frases') and g.get('personaje') and (a.num == g['num'] if a.num else g['num'] not in hechos)]
    os.makedirs(f'{R}/avatar-ia/personajes', exist_ok=True); os.makedirs(a.salida, exist_ok=True)
    cambio = False
    for g in cola[:a.max]:
        print(f'▶ guion {g["num"]} ({g["personaje"]})', flush=True)
        img = f'{R}/avatar-ia/personajes/{g["personaje"]}.jpg'
        if not os.path.exists(img): foto(g, img)
        tmp = f'{R}/trabajo/avatar-ia/{g["num"]}'; os.makedirs(tmp, exist_ok=True)
        marcas, total = voz(g, f'{tmp}/voz.wav')
        video(img, f'{tmp}/voz.wav', f'{a.salida}/{g["num"]}.mp4', f'{tmp}/st')
        # capturas: cada una arranca con la frase que indica "frase" y dura hasta la siguiente indicada (o el CTA)
        caps = g.get('capturas_frase')
        if caps:
            g['capturas'] = [{'img': c['img'], 'desde': marcas[c['frase']],
                              'hasta': marcas[c['hasta_frase']] if c.get('hasta_frase') is not None else marcas[-1]} for c in caps]
            cambio = True
        print('✓', g['num'], total, 's', flush=True)
    if cambio: json.dump(pend, open(P, 'w'), ensure_ascii=False, indent=1)
    if not cola: print('No hay guiones de avatar pendientes sin video.')


if __name__ == '__main__':
    main()
