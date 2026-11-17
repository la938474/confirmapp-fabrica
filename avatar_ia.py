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
import argparse, base64, json, os, subprocess, sys, urllib.error, urllib.request

R = os.path.dirname(os.path.abspath(__file__))
ST = os.environ.get('SADTALKER', f'{R}/../SadTalker')
PY_ST = os.environ.get('SADTALKER_PY', sys.executable)
NEG = (', waist-up shot, standing, both hands visible in front of the body at waist level, natural relaxed pose, '
       'looking directly at camera, gentle friendly smile, face well lit, only one person, softly blurred background, '
       'no text, no signs, no logos, photorealistic, natural skin texture, shot on 50mm lens')


def sh(*a, **k):
    subprocess.run(a, check=True, **k)


def _cf(cuenta, token, modelo, cuerpo):
    url = f'https://api.cloudflare.com/client/v4/accounts/{cuenta}/ai/run/{modelo}'
    req = urllib.request.Request(url, json.dumps(cuerpo).encode(),
                                 {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=180)
        return r.headers.get('Content-Type', ''), r.read()
    except urllib.error.HTTPError as e:
        print(f'  Cloudflare {modelo}: {e.code} {e.read()[:500]!r}', flush=True)
        return None, None


def _imagen(tipo, datos):
    """Saca los bytes de la imagen de la respuesta de Cloudflare (JSON con base64 o imagen directa)."""
    if not datos: return None
    if 'json' in (tipo or ''):
        res = json.loads(datos).get('result') or {}
        b64 = res.get('image') if isinstance(res, dict) else None
        return base64.b64decode(b64) if b64 else None
    return datos


def foto(g, ruta):
    """Foto vertical de medio cuerpo (manos visibles, para que HeyGen anime el cuerpo) con Cloudflare Workers AI."""
    cuenta, token = os.environ.get('CF_ACCOUNT_ID', '').strip(), os.environ.get('CF_API_TOKEN', '').strip()
    prompt = g['foto_prompt'] + NEG
    malo = 'text, watermark, logo, deformed hands, extra fingers, cropped head, close-up, blurry face, cartoon'
    intentos = [  # primero modelos que aceptan tamaño vertical; al final FLUX (cuadrado) y SDXL
        ('@cf/leonardo/lucid-origin', {'prompt': prompt, 'width': 832, 'height': 1472}),
        ('@cf/leonardo/phoenix-1.0', {'prompt': prompt, 'negative_prompt': malo, 'width': 832, 'height': 1472}),
        ('@cf/black-forest-labs/flux-1-schnell', {'prompt': prompt, 'steps': 8}),
        ('@cf/stabilityai/stable-diffusion-xl-base-1.0', {'prompt': prompt, 'negative_prompt': malo, 'width': 768, 'height': 1344, 'num_steps': 20}),
    ]
    datos = None
    for modelo, cuerpo in intentos:
        datos = _imagen(*_cf(cuenta, token, modelo, cuerpo))
        if datos: print('  foto con', modelo, flush=True); break
    if not datos: sys.exit('Cloudflare no generó la foto (ver mensajes arriba).')
    tmp = ruta + '.tmp'; open(tmp, 'wb').write(datos)
    from PIL import Image, ImageFilter
    im = Image.open(tmp).convert('RGB'); w, h = im.size
    if h / w >= 1.6:   # ya es vertical
        cw = min(w, round(h * 9 / 16)); x = (w - cw) // 2
        im = im.crop((x, 0, x + cw, h)).resize((1080, 1920), Image.LANCZOS)
    else:              # cuadrada: la pongo abajo sobre un fondo extendido (no recorto el cuerpo)
        lado = im.resize((1080, round(h * 1080 / w)), Image.LANCZOS)
        fondo = im.resize((1080, 1920), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
        fondo.paste(lado, (0, 1920 - lado.height)); im = fondo
    im.save(ruta, quality=95); os.remove(tmp)
    print('  foto generada:', ruta, flush=True)


def voz(g, ruta):
    sys.path.insert(0, f'{R}/tts'); sys.path.insert(0, R)
    import kok, fabrica
    partes = []
    frases = g['frases'][:1] if os.environ.get('AVATAR_CORTA') == '1' else g['frases']
    for i, t in enumerate(frases):
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
    from PIL import Image
    chica = f'{tmp}/foto.jpg'  # 576x1024 basta para el celular y acelera mucho en CPU
    Image.open(img).convert('RGB').resize((576, 1024), Image.LANCZOS).save(chica, quality=95)
    mejora = ['--enhancer', 'gfpgan'] if os.environ.get('AVATAR_MEJORA') == '1' else []
    lim = os.environ.get('AVATAR_LIMITE', '150m')  # para que nunca se quede colgado sin dejar registro
    sh('timeout', lim, PY_ST, '-u', 'inference.py', '--driven_audio', wav, '--source_image', chica, '--result_dir', tmp,
       '--still', '--preprocess', 'full', *mejora, '--cpu', '--batch_size', '8', cwd=ST)
    mp4 = sorted((os.path.join(dp, f) for dp, _, fs in os.walk(tmp) for f in fs if f.endswith('.mp4')), key=os.path.getmtime)[-1]
    # SadTalker devuelve audio en 16 kHz; lo volvemos a pegar en buena calidad
    sh('ffmpeg', '-y', '-v', 'error', '-i', mp4, '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p',
       '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-movflags', '+faststart', salida)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=2); ap.add_argument('--num', type=int)
    ap.add_argument('--salida', default=f'{R}/avatar')
    ap.add_argument('--rehacer-fotos', action='store_true', help='vuelve a generar la foto aunque exista (menos medico)')
    ap.add_argument('--kit', action='store_true', help='solo foto + voz para hacerlo a mano en HeyGen (kit-heygen/)')
    a = ap.parse_args()
    P = f'{R}/guiones-avatar/pendientes.json'
    pend = json.load(open(P))
    hechos = {int(f.split('.')[0].split(' ')[0]) for f in os.listdir(f'{R}/avatar') if f[:1].isdigit()}
    kits = {int(d.split('-')[0]) for d in os.listdir(f'{R}/kit-heygen') if d[:1].isdigit()} if os.path.isdir(f'{R}/kit-heygen') else set()
    cola = [g for g in pend if g.get('frases') and g.get('personaje') and
            (a.num == g['num'] if a.num else g['num'] not in hechos and not (a.kit and g['num'] in kits))]
    os.makedirs(f'{R}/avatar-ia/personajes', exist_ok=True); os.makedirs(a.salida, exist_ok=True)
    cambio, rehechas = False, set()
    for g in cola[:a.max]:
        print(f'▶ guion {g["num"]} ({g["personaje"]})', flush=True)
        img = f'{R}/avatar-ia/personajes/{g["personaje"]}.jpg'
        if a.rehacer_fotos and g['personaje'] != 'medico' and os.path.exists(img) and img not in rehechas:
            os.remove(img); rehechas.add(img)
        if not os.path.exists(img):
            if not (os.environ.get('CF_ACCOUNT_ID') and os.environ.get('CF_API_TOKEN')):
                print(f'  (sin foto de {g["personaje"]} y sin Cloudflare: lo salto)'); continue
            foto(g, img)
        tmp = f'{R}/trabajo/avatar-ia/{g["num"]}'; os.makedirs(tmp, exist_ok=True)
        marcas, total = voz(g, f'{tmp}/voz.wav')
        if a.kit:
            k = f'{R}/kit-heygen/{g["num"]}-{g["personaje"]}'; os.makedirs(k, exist_ok=True)
            from PIL import Image
            Image.open(img).convert('RGB').resize((1080, 1920), Image.LANCZOS).save(f'{k}/foto.jpg', quality=95)
            sh('ffmpeg', '-y', '-v', 'error', '-i', f'{tmp}/voz.wav', '-ar', '44100', '-b:a', '192k', f'{k}/voz.mp3')
            open(f'{k}/LEEME.txt', 'w').write(
                f'Guion {g["num"]} · {g["personaje"]} · {total} s\n\nEn HeyGen: avatar con foto.jpg, video vertical 9:16, '
                f'pestaña Audio → sube voz.mp3, genera en 720p.\nDescárgalo, nómbralo {g["num"]}.mp4 y súbelo a la carpeta avatar/.\n\n'
                'Lo que dice:\n' + '\n'.join(g['frases']) + '\n')
        else:
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
