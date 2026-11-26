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
import argparse, base64, datetime, json, os, subprocess, sys, urllib.error, urllib.request

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


def video(img, wav, salida, tmp, cara=None):
    """Avatar gratis (SadTalker en CPU, sin HeyGen). Para que se vea nítido: anima solo un recorte cuadrado de la
    cabeza en alta resolución (con GFPGAN que afina la cara) y lo vuelve a pegar, con bordes suaves, sobre la foto
    original 1080x1920. Así el fondo y el cuerpo quedan en calidad completa y la cara se ve bien en el círculo."""
    os.makedirs(tmp, exist_ok=True)
    from PIL import Image
    foto = Image.open(img).convert('RGB').resize((1080, 1920), Image.LANCZOS); foto.save(f'{tmp}/full.jpg', quality=95)
    cx, cy, r = cara or [540, 520, 250]
    L = min(1080, int(r * 2.9)) // 2 * 2                  # cuadro con cabeza, cuello y un poco de hombros
    x0 = max(0, min(1080 - L, cx - L // 2)); y0 = max(0, min(1920 - L, int(cy - L * .42)))
    foto.crop((x0, y0, x0 + L, y0 + L)).resize((512, 512), Image.LANCZOS).save(f'{tmp}/cabeza.png')
    mejora = [] if os.environ.get('AVATAR_MEJORA') == '0' else ['--enhancer', 'gfpgan']
    lim = os.environ.get('AVATAR_LIMITE', '150m')  # para que nunca se quede colgado sin dejar registro
    sh('timeout', lim, PY_ST, '-u', 'inference.py', '--driven_audio', wav, '--source_image', f'{tmp}/cabeza.png', '--result_dir', tmp,
       '--still', '--preprocess', 'full', *mejora, '--cpu', '--batch_size', '8', cwd=ST)
    mp4 = sorted((os.path.join(dp, f) for dp, _, fs in os.walk(tmp) for f in fs if f.endswith('.mp4')), key=os.path.getmtime)[-1]
    # máscara de bordes suaves para pegar la cabeza animada sobre la foto
    from PIL import ImageDraw, ImageFilter
    m = Image.new('L', (L, L), 0); f = int(L * .09)
    ImageDraw.Draw(m).rounded_rectangle((f, f, L - f, L - f), int(L * .2), fill=255)
    m.filter(ImageFilter.GaussianBlur(f * .7)).save(f'{tmp}/mascara.png')
    # SadTalker devuelve audio en 16 kHz; lo volvemos a pegar en buena calidad (wav original)
    sh('ffmpeg', '-y', '-v', 'error', '-loop', '1', '-i', f'{tmp}/full.jpg', '-i', mp4, '-loop', '1', '-i', f'{tmp}/mascara.png', '-i', wav,
       '-filter_complex', f"[1:v]scale={L}:{L}:flags=lanczos,fps=30,format=rgba[c];[2:v]format=gray[m];[c][m]alphamerge[cm];"
       f"[0:v]fps=30,format=rgba[f];[f][cm]overlay={x0}:{y0}:shortest=1,format=yuv420p[v]",
       '-map', '[v]', '-map', '3:a', '-shortest', '-c:v', 'libx264', '-crf', '18', '-preset', 'medium',
       '-c:a', 'aac', '-b:a', '160k', '-ar', '44100', '-movflags', '+faststart', salida)


# ---------- HeyGen (API, pago por uso) ----------
HG = 'https://api.heygen.com'


def _hg(metodo, ruta, cuerpo=None, archivo=None):
    llave = os.environ['HEYGEN_API_KEY'].strip()
    h = {'X-Api-Key': llave, 'Accept': 'application/json'}
    datos = None
    if archivo:
        frontera = 'confirmapp' + os.urandom(8).hex()
        tipo = 'image/jpeg' if archivo.endswith('.jpg') else 'audio/mpeg'
        datos = (f'--{frontera}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(archivo)}"\r\n'
                 f'Content-Type: {tipo}\r\n\r\n').encode() + open(archivo, 'rb').read() + f'\r\n--{frontera}--\r\n'.encode()
        h['Content-Type'] = f'multipart/form-data; boundary={frontera}'
    elif cuerpo is not None:
        datos = json.dumps(cuerpo).encode(); h['Content-Type'] = 'application/json'
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(HG + ruta, datos, h, method=metodo), timeout=300))
    except urllib.error.HTTPError as e:
        sys.exit(f'HeyGen {metodo} {ruta}: {e.code} {e.read()[:800]!r}')


def heygen(g, img, wav, salida):
    """Video Avatar IV (foto + nuestro audio, vertical 9:16) con la API de HeyGen."""
    import time
    mp3 = wav[:-4] + '.mp3'
    sh('ffmpeg', '-y', '-v', 'error', '-i', wav, '-ar', '44100', '-b:a', '192k', mp3)
    jpg = wav[:-4] + '_foto.jpg'
    from PIL import Image
    Image.open(img).convert('RGB').save(jpg, quality=95)
    vid = os.environ.get('HEYGEN_VIDEO_ID', '').strip()  # para volver a bajar un video ya pagado
    if vid: return _bajar(vid, salida)
    foto_id = _hg('POST', '/v3/assets', archivo=jpg)['data']['asset_id']
    audio_id = _hg('POST', '/v3/assets', archivo=mp3)['data']['asset_id']
    r = _hg('POST', '/v3/videos', {
        'type': 'image', 'image': {'type': 'asset_id', 'asset_id': foto_id}, 'audio_asset_id': audio_id,
        'aspect_ratio': '9:16', 'resolution': '720p', 'title': f'Confirmapp {g["id"]}',
        'motion_prompt': 'Natural, friendly hand gestures while explaining, small head nods, relaxed shoulders, keeps looking at the camera.',
        'expressiveness': 'medium'})
    vid = r['data']['video_id']; print('  HeyGen video', vid, flush=True)
    _bajar(vid, salida)


def _bajar(vid, salida):
    import time
    for _ in range(120):  # hasta 40 min
        d = _hg('GET', f'/v3/videos/{vid}').get('data', {})
        st = d.get('status')
        if st in ('completed', 'success'):
            urllib.request.urlretrieve(d['video_url'], salida); return
        if st in ('failed', 'error'): sys.exit(f'HeyGen falló: {json.dumps(d)[:800]}')
        time.sleep(20)
    sys.exit('HeyGen tardó demasiado')


def cara(video):
    """Centro y radio de la cara (en el cuadro 1080x1920) para el círculo del estilo grande."""
    try:
        return _cara(video)
    except Exception as e:
        print('  (no pude detectar la cara, uso la posición normal):', e); return [540, 520, 250]


def _cara(video):
    import cv2
    c = cv2.VideoCapture(video); c.set(cv2.CAP_PROP_POS_MSEC, 800); ok, f = c.read()
    if not ok: return [540, 520, 250]
    h, w = f.shape[:2]; cw = min(w, round(h * 9 / 16)); x0 = (w - cw) // 2
    f = cv2.resize(f[:, x0:x0 + cw], (1080, 1920))
    det = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    caras = det.detectMultiScale(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), 1.1, 6, minSize=(100, 100))
    if not len(caras): return [540, 520, 250]
    x, y, a, b = max(caras, key=lambda r: r[2] * r[3])
    return [int(x + a / 2), int(y + b / 2 - b * 0.08), int(max(a, b) * 0.95)]


def pantallas_a_capturas(pantallas, marcas, total, giro):
    """Convierte lo que debe verse en cada frase en capturas con tiempos reales.
    Valores: null (sin celular), "autoagenda:link" / "autoagenda:elige" / "autoagenda:aviso", "recordatorio",
    "cta" (prueba gratis) o el nombre de una captura (k_gcal, k_chat, k_magic, m_pSusc, m_pAutoMenu…)."""
    fin = marcas + [total]; caps = []; i = 0
    G = json.load(open(f'{R}/assets/giros.json')).get(giro, {})
    nombres = G.get('nombres', 'Ana López|Sofía Mena|Laura Paz|Mariana Ruiz').split('|')
    while i < len(pantallas):
        p = pantallas[i]
        if p and p.startswith('autoagenda'):
            j = i
            while j + 1 < len(pantallas) and (pantallas[j + 1] or '').startswith('autoagenda'): j += 1
            a = fin[i]; tramo = pantallas[i:j + 1]
            p1 = next((fin[i + k] for k, x in enumerate(tramo) if x == 'autoagenda:elige'), a + (fin[j + 1] - a) * .3) - a
            p2 = next((fin[i + k] for k, x in enumerate(tramo) if x == 'autoagenda:aviso'), a + (fin[j + 1] - a) * .7) - a
            q = {'p1': round(p1, 2), 'p2': round(p2, 2), 'cliente': nombres[3]}
            q['pill2'] = G.get('pill2') or f"Tu {G.get('cliente', 'cliente')} elige su horario libre"
            if G.get('emoji'): q['emoji'] = G['emoji']
            caps.append({'anim': 'autoagenda', 'desde': round(a, 2), 'hasta': round(fin[j + 1], 2), 'q': q}); i = j + 1; continue
        j = i
        while j + 1 < len(pantallas) and pantallas[j + 1] == p: j += 1  # frases seguidas con la misma pantalla
        if p in ('autochat', 'lealtad'):  # animaciones "en vivo"; p1 = cuándo empieza la 2a frase (ahí cambia la escena)
            q = {'cliente': nombres[0]}
            if j > i: q['p1'] = round(fin[i + 1] - fin[i], 2)
            if p == 'lealtad': q['premio'] = G.get('premio', 'Un corte gratis' if giro == 'barberia' else 'tu premio')
            caps.append({'anim': p, 'desde': round(fin[i], 2), 'hasta': round(fin[j + 1], 2), 'q': q})
        elif p == 'recordatorio':
            caps.append({'anim': 'recordatorio', 'desde': round(fin[i], 2), 'hasta': round(fin[j + 1], 2), 'q': {'clientes': '|'.join(nombres), 'rcliente': nombres[1]}})
        elif p == 'cta':
            caps.append({'img': '01_login', 'desde': round(fin[i], 2), 'hasta': round(fin[j + 1], 2)})
        elif p:
            caps.append({'img': p, 'desde': round(fin[i], 2), 'hasta': round(fin[j + 1], 2)})
        i = j + 1
    # une tramos seguidos de la misma imagen
    out = []
    for c in caps:
        if out and c.get('img') and out[-1].get('img') == c['img'] and abs(out[-1]['hasta'] - c['desde']) < .05: out[-1]['hasta'] = c['hasta']
        else: out.append(c)
    return out


def mes_heygen():
    f = f'{R}/avatar-ia/heygen_mes.json'
    d = json.load(open(f)) if os.path.exists(f) else {}
    return f, d, datetime.date.today().strftime('%Y-%m')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=2); ap.add_argument('--num', type=int)
    ap.add_argument('--salida', default=f'{R}/avatar')
    ap.add_argument('--rehacer-fotos', action='store_true', help='vuelve a generar la foto aunque exista (menos medico)')
    ap.add_argument('--heygen', action='store_true', help='video con la API de HeyGen (Avatar IV)')
    ap.add_argument('--kit', action='store_true', help='solo foto + voz para hacerlo a mano en HeyGen (kit-heygen/)')
    a = ap.parse_args()
    P = f'{R}/guiones-avatar/pendientes.json'
    pend = json.load(open(P))
    hechos = {int(f.split('.')[0].split(' ')[0]) for f in os.listdir(f'{R}/avatar') if f[:1].isdigit()}
    kits = {int(d.split('-')[0]) for d in os.listdir(f'{R}/kit-heygen') if d[:1].isdigit()} if os.path.isdir(f'{R}/kit-heygen') else set()
    cola = [g for g in pend if g.get('frases') and g.get('personaje') and
            (a.num == g['num'] if a.num else g['num'] not in hechos and not (a.kit and g['num'] in kits))]
    os.makedirs(f'{R}/avatar-ia/personajes', exist_ok=True); os.makedirs(a.salida, exist_ok=True)
    cambio, rehechas, sin_credito = False, set(), False
    for g in cola[:a.max]:
        print(f'▶ guion {g["num"]} ({g["personaje"]})', flush=True)
        img = f'{R}/avatar-ia/personajes/{g["personaje"]}.jpg'
        if a.rehacer_fotos and g['personaje'] != 'medico' and os.path.exists(img) and img not in rehechas:
            os.remove(img); rehechas.add(img)
        if not os.path.exists(img) and g.get('foto_de_luis'):
            print(f'  (falta la foto de {g["personaje"]} que hizo Luis: lo salto)'); continue
        if not os.path.exists(img):
            if not (os.environ.get('CF_ACCOUNT_ID') and os.environ.get('CF_API_TOKEN')):
                print(f'  (sin foto de {g["personaje"]} y sin Cloudflare: lo salto)'); continue
            foto(g, img)
        tmp = f'{R}/trabajo/avatar-ia/{g["num"]}'; os.makedirs(tmp, exist_ok=True)
        marcas, total = voz(g, f'{tmp}/voz.wav')
        usar_kit = a.kit or sin_credito
        if a.heygen and not usar_kit:
            fm, dm, mes = mes_heygen(); tope = int(os.environ.get('HEYGEN_MAX_MES', '12'))
            if dm.get(mes, 0) >= tope: print(f'  tope del mes alcanzado ({tope} videos); lo dejo para el próximo mes'); break
            try:
                heygen(g, img, f'{tmp}/voz.wav', f'{a.salida}/{g["num"]}.mp4')
            except SystemExit as e:
                if 'INSUFFICIENT_CREDIT' not in str(e): raise
                # Sin créditos de API en HeyGen: en vez de fallar, dejo el kit (foto + voz) para hacerlo a mano
                print('  HeyGen sin créditos de API: dejo el kit para hacerlo a mano', flush=True)
                sin_credito = True; usar_kit = True
            else:
                dm[mes] = dm.get(mes, 0) + 1; json.dump(dm, open(fm, 'w'), indent=1)
                g['estilo'] = g.get('estilo', 'grande'); g['cara'] = cara(f'{a.salida}/{g["num"]}.mp4'); cambio = True
        if usar_kit:
            k = f'{R}/kit-heygen/{g["num"]}-{g["personaje"]}'; os.makedirs(k, exist_ok=True)
            from PIL import Image
            Image.open(img).convert('RGB').resize((1080, 1920), Image.LANCZOS).save(f'{k}/foto.jpg', quality=95)
            sh('ffmpeg', '-y', '-v', 'error', '-i', f'{tmp}/voz.wav', '-ar', '44100', '-b:a', '192k', f'{k}/voz.mp3')
            open(f'{k}/LEEME.txt', 'w').write(
                f'Guion {g["num"]} · {g["personaje"]} · {total} s\n\nEn HeyGen: avatar con foto.jpg, video vertical 9:16, '
                f'pestaña Audio → sube voz.mp3, genera en 720p.\nDescárgalo, nómbralo {g["num"]}.mp4 y súbelo a la carpeta avatar/.\n\n'
                'Lo que dice:\n' + '\n'.join(g['frases']) + '\n')
        elif a.heygen:
            pass
        else:
            video(img, f'{tmp}/voz.wav', f'{a.salida}/{g["num"]}.mp4', f'{tmp}/st', g.get('cara'))
        # capturas: cada una arranca con la frase que indica "frase" y dura hasta la siguiente indicada (o el CTA)
        if g.get('pantallas'):
            g['capturas'] = pantallas_a_capturas(g['pantallas'], marcas, total, g['giro']); g['capturas_revisadas'] = True; cambio = True
        caps = g.get('capturas_frase')
        if caps and not g.get('pantallas'):
            fin = marcas + [total]  # hasta_frase = len(frases) significa "hasta el final"
            g['capturas'] = [{'img': c['img'], 'desde': fin[c['frase']],
                              'hasta': fin[c['hasta_frase']] if c.get('hasta_frase') is not None else fin[-1]} for c in caps]
            cambio = True
        print('✓', g['num'], total, 's', flush=True)
    if cambio: json.dump(pend, open(P, 'w'), ensure_ascii=False, indent=1)
    if not cola: print('No hay guiones de avatar pendientes sin video.')


if __name__ == '__main__':
    main()
