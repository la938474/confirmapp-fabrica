"""Fábrica de videos Confirmapp.

  python3 fabrica.py hacer guiones/AAAA-MM-DD.json   → valida y arma los videos en salida/
  python3 fabrica.py avatares                        → toma los .mp4 de avatar/, los prepara y los deja en salida/
  python3 fabrica.py publicar                        → sube salida/ a la rama "cola" (Supabase la importa sola)
                                                       y anota los ganchos en historial.json
"""
import glob, json, os, re, shutil, subprocess, sys, datetime, urllib.parse

R = os.path.dirname(os.path.abspath(__file__))
A = f'{R}/assets'
GIROS = json.load(open(f'{A}/giros.json'))
CAPS = {'01_login', '02_giro', '03_datos', '04_prueba', '05_google', 'k_chat', 'k_gcal', 'k_magic', 'm_pAutoMenu', 'm_pSusc'}
ESPECIALES = {'HOOK', 'FRASE', 'LISTA', 'CTA'}
VOCES = {'dora_brillante', 'alex_grave'}
FILTRO_VOZ = ('silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,'
              'areverse,afade=t=in:d=0.02,highpass=f=70,acompressor=threshold=-20dB:ratio=3:attack=5:release=80,loudnorm=I=-14:TP=-1.5')


def sh(*a, **k):
    subprocess.run(a, check=True, **k)


def dur(f):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]))


def validar(v):
    err = []
    for k in ('id', 'giro', 'gancho', 'texto', 'escenas'):
        if not v.get(k): err.append(f'falta "{k}"')
    if err: return err
    if not re.fullmatch(r'[a-z0-9_-]{4,60}', v['id']): err.append('id: solo minúsculas, números, _ y - (4-60)')
    if v['giro'] not in GIROS: err.append(f'giro desconocido: {v["giro"]} (usa: {", ".join(GIROS)})')
    if v.get('voz', 'dora_brillante') not in VOCES: err.append(f'voz: usa {VOCES}')
    if not 1.0 <= float(v.get('velocidad', 1.12)) <= 1.25: err.append('velocidad entre 1.0 y 1.25')
    if len(v['texto']) > 2000: err.append('texto (caption) muy largo')
    E = v['escenas']
    if not 3 <= len(E) <= 8: err.append('entre 3 y 8 escenas')
    if E and E[-1].get('img') != 'CTA': err.append('la última escena debe ser CTA')
    for i, e in enumerate(E):
        img = e.get('img')
        if img not in CAPS | ESPECIALES: err.append(f'escena {i}: img "{img}" no existe')
        if str(e.get('e', '')).startswith('ilus:') and not os.path.exists(f"{A}/ilus/{e['e'][5:]}.svg"): err.append(f'escena {i}: no existe assets/ilus/{e["e"][5:]}.svg')
        if not e.get('v'): err.append(f'escena {i}: falta "v" (lo que dice la voz)')
        if len(e.get('v', '')) > 260: err.append(f'escena {i}: voz muy larga')
        if img == 'LISTA' and not 2 <= len(e.get('s', '').split('|')) <= 4: err.append(f'escena {i}: LISTA lleva 2-4 puntos en "s" separados por |')
    total = sum(len(e.get('v', '')) for e in E)
    if total > 900: err.append(f'el video quedaría muy largo ({total} letras de voz; máximo 900 ≈ 45 s)')
    return err


def hacer(ruta):
    vids = json.load(open(ruta))
    malos = {v.get('id', '?'): validar(v) for v in vids}
    malos = {k: e for k, e in malos.items() if e}
    if malos:
        for k, e in malos.items(): print('✗', k, '→', '; '.join(e))
        sys.exit(1)
    sys.path.insert(0, f'{R}/tts'); import kok
    os.makedirs(f'{R}/salida', exist_ok=True)
    for v in vids:
        g = GIROS[v['giro']]
        d = f'{R}/trabajo/{v["id"]}'
        shutil.rmtree(d, ignore_errors=True)
        for s in ('img', 'esc', 'audio'): os.makedirs(f'{d}/{s}')
        os.symlink(f'{A}/giros/{g["capturas"]}', f'{d}/cap')
        os.symlink(f'{A}/ilus', f'{d}/ilus')
        shutil.copy(f'{A}/frame.html', d); shutil.copy(f'{A}/icon-192.png', d)
        E = v['escenas']
        json.dump(E, open(f'{d}/guion.json', 'w'), ensure_ascii=False)
        colores = {k: g[k] for k in ('c2', 'c3', 'bg')} | {'c': g['color']}
        js = f"""const {{chromium}}=require('playwright');const G=require('{d}/guion.json');const C={json.dumps(colores)};
(async()=>{{const b=await chromium.launch();const p=await b.newPage({{viewport:{{width:1080,height:1920}}}});
for(let i=0;i<G.length;i++){{const e=G[i];const q=new URLSearchParams({{img:e.img,t:e.t||'',s:e.s||'',n:e.n||'',e:e.e||'',...C}});
await p.goto('file://{d}/frame.html?'+q);await p.waitForTimeout(350);
await p.screenshot({{path:'{d}/img/'+i+'.jpg',type:'jpeg',quality:92}});}}
await b.close();}})();"""
        open(f'{d}/frames.js', 'w').write(js)
        sh('node', f'{d}/frames.js')
        voz, vel = v.get('voz', 'dora_brillante'), float(v.get('velocidad', 1.12))
        for i, e in enumerate(E):
            raw = f'{d}/audio/raw{i}.wav'
            kok.guardar(kok.decir(e['v'], voz, vel), raw)
            sh('ffmpeg', '-y', '-v', 'error', '-i', raw, '-af', FILTRO_VOZ, '-ar', '44100', '-ac', '1', f'{d}/audio/{i}.wav')
        render(d, len(E), f'{R}/salida/{v["id"]}.mp4', float(v.get('zoom', 0.09)), [e['v'] for e in E])
        json.dump({k: v[k] for k in ('id', 'giro', 'gancho', 'texto')} | {'formato': v.get('formato', ''), 'voz': voz},
                  open(f'{R}/salida/{v["id"]}.json', 'w'), ensure_ascii=False)
        print('✓', v['id'], round(dur(f'{R}/salida/{v["id"]}.mp4'), 1), 's', flush=True)


def render(d, n, salida, zoom, voces=None):
    vs, aus, ini = [], [], []
    for i in range(n):
        a = dur(f'{d}/audio/{i}.wav')
        ex = 1.6 if i == n - 1 else 0.3
        N = int(round((a + ex) * 30)); D = N / 30
        tmp = f'{d}/esc/tmp_{i}.mp4'
        sh('ffmpeg', '-y', '-v', 'error', '-i', f'{d}/img/{i}.jpg', '-vf',
           f"zoompan=z='1+{zoom}*on/{N}+0.06*max(0,1-on/7)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={N}:s=1080x1920:fps=30,format=yuv420p,"
           + (f"fade=in:st=0:d=0.15," if i else "") + f"fade=out:st={round(D - 0.15, 3)}:d=0.15",  # escena 0 sin fundido: el primer cuadro es la portada
           '-frames:v', str(N), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p', tmp)
        os.rename(tmp, f'{d}/esc/{i}.mp4')
        sh('ffmpeg', '-y', '-v', 'error', '-i', f'{d}/audio/{i}.wav', '-af', f'adelay=200|200,apad=whole_dur={D}', '-ar', '44100', '-ac', '2', f'{d}/esc/{i}.wav')
        ini.append((sum(x[1] for x in ini), D, a))  # (inicio, duración escena, duración voz)
        vs.append(f"file '{i}.mp4'"); aus.append(f"file '{i}.wav'")
    open(f'{d}/esc/v.txt', 'w').write('\n'.join(vs)); open(f'{d}/esc/a.txt', 'w').write('\n'.join(aus))
    sh('ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', f'{d}/esc/v.txt', '-c', 'copy', f'{d}/esc/v.mp4')
    sh('ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', f'{d}/esc/a.txt', '-c:a', 'pcm_s16le', f'{d}/esc/voz.wav')
    D = dur(f'{d}/esc/v.mp4')
    # ---- Estilo PRO: subtítulos palabra por palabra + brillo que cruza + efectos de sonido ----
    video = f'{d}/esc/v.mp4'
    if voces:
        subtitulos(d, ini, voces, f'{d}/esc/subs.ass')
        luz = brillo(f'{d}/esc/luz.png')
        tmpv = f'{d}/esc/vpro.tmp.mp4'
        sh('ffmpeg', '-y', '-v', 'error', '-i', video, '-loop', '1', '-i', luz, '-filter_complex',
           f"[1:v]format=rgba[l];[0:v][l]overlay=x='mod(t*320,2300)-700':y=-300:shortest=1,ass={d}/esc/subs.ass,format=yuv420p[o]",
           '-map', '[o]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', tmpv)
        os.rename(tmpv, f'{d}/esc/vpro.mp4'); video = f'{d}/esc/vpro.mp4'
        efectos(ini, D, f'{d}/esc/sfx.wav')
        entradas = ['-i', f'{d}/esc/voz.wav', '-i', f'{A}/musica.wav', '-i', f'{d}/esc/sfx.wav']
        mezcla = "[md][v2][2:a]amix=inputs=3:normalize=0,alimiter=limit=0.95[o]"
    else:
        entradas = ['-i', f'{d}/esc/voz.wav', '-i', f'{A}/musica.wav']
        mezcla = "[md][v2]amix=inputs=2:normalize=0,alimiter=limit=0.95[o]"
    sh('ffmpeg', '-y', '-v', 'error', *entradas, '-filter_complex',
       f"[1:a]volume=0.3,atrim=0:{D},afade=t=in:d=0.5,afade=t=out:st={D - 1.5}:d=1.5,aformat=channel_layouts=stereo[m];[0:a]asplit[v1][v2];"
       "[m][v1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[md];" + mezcla,
       '-map', '[o]', '-ar', '44100', f'{d}/esc/mix.wav')
    tmp = salida[:-4] + '.tmp.mp4'
    sh('ffmpeg', '-y', '-v', 'error', '-i', video, '-i', f'{d}/esc/mix.wav', '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
       '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', tmp)
    os.rename(tmp, salida)
    shutil.copy(f'{d}/img/0.jpg', salida[:-4] + '.jpg')  # portada = primera escena


# ---------------- Estilo PRO (subtítulos, brillo, efectos) ----------------
MOSTRAR = [(r'confirm ap punto com punto eme equis', 'confirmapp.com.mx'), (r'confirchat i a', 'ConfirChat IA'), (r'confirm ap', 'Confirmapp'),
           (r'guatsap', 'WhatsApp'), (r'gúgol', 'Google'), (r'áutluk', 'Outlook'), (r'máyic', 'Magic'), (r'\bsiete días', '7 días')]
PESO = {'confirmapp.com.mx': 10, 'confirmapp': 3, 'whatsapp': 2, 'confirchat': 3, 'ia': 2, '7': 2}


def mostrar(v):
    """Texto de la voz (fonético) → texto para leer en pantalla."""
    for a, b in MOSTRAR: v = re.sub(a, b, v, flags=re.I)
    return v


def silabas(w):
    k = w.lower().strip('.,:;¿?¡!')
    return PESO.get(k, max(1, len(re.findall(r'[aeiouáéíóúü]+', k))))


def tramos_voz(wav, a):
    """Tramos hablados (inicio, fin) dentro del audio ya recortado de silencios."""
    r = subprocess.run(['ffmpeg', '-i', wav, '-af', 'silencedetect=n=-40dB:d=0.12', '-f', 'null', '-'], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', r)]; en = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', r)]
    out, x = [], 0.0
    for s0, s1 in zip(st, en):
        if s0 > x + 0.05 and s1 < a - 0.05: out.append((x, s0)); x = s1
    out.append((x, a)); return out


def subtitulos(d, ini, voces, ass):
    """ASS con 2-3 palabras a la vez; la palabra que se dice va en dorado y el grupo entra con un pequeño rebote."""
    palabras = []  # (texto, t0, t1, grupo, fin_escena)
    g = 0
    for i, ((t_esc, D, a), v) in enumerate(zip(ini, voces)):
        base = t_esc + 0.2
        frases = [f.strip().replace('·', '.') for f in re.findall(r'[^,.:;?!]+[,.:;?!]*', mostrar(v).replace('confirmapp.com.mx', 'confirmapp·com·mx')) if f.strip()]
        tr = tramos_voz(f'{d}/audio/{i}.wav', a)
        if len(tr) != len(frases):  # si no cuadran las pausas, reparte por sílabas
            tot = sum(silabas(w) for f in frases for w in f.split()); tr, x = [], 0.0
            for f in frases:
                dd = a * sum(silabas(w) for w in f.split()) / tot; tr.append((x, x + dd)); x += dd
        for (x0, x1), f in zip(tr, frases):
            ws = f.split(); pes = [silabas(w) for w in ws]; T = sum(pes); x = x0; n = 0
            for w, p in zip(ws, pes):
                dd = (x1 - x0) * p / T
                palabras.append((w, base + x, base + x + dd, g, t_esc + D)); x += dd; n += 1
                if n == 3: g += 1; n = 0
            if n: g += 1
    escribir_ass(palabras, ass)


def escribir_ass(palabras, ass, posicion=None):
    """palabras: [(texto, t0, t1, grupo, fin_max)]. posicion(t) → None (abajo) o (x, y, tamaño) para mover el subtítulo."""
    def ts(t):
        t = max(0, t); return f'{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}'
    ev = []
    grupos = sorted({p[3] for p in palabras})
    for gi in grupos:
        ws = [p for p in palabras if p[3] == gi]
        sig = next((p[1] for p in palabras if p[3] > gi), 1e9)
        fin = min(ws[-1][2] + 0.3, sig - 0.07, ws[-1][4] - 0.05)
        for k, w in enumerate(ws):
            t0 = w[1] - (0.05 if k == 0 else 0); t1 = ws[k + 1][1] if k + 1 < len(ws) else fin
            if t1 <= t0: continue
            txt = ' '.join((r'{\c&H6AC4E9&\fscx112\fscy112}' + x[0].rstrip(',.:;') + r'{\c&HFFFFFF&\fscx100\fscy100}') if j == k
                           else x[0].rstrip(',.:;') for j, x in enumerate(ws))
            pop = r'{\fscx80\fscy80\t(0,130,\fscx100\fscy100)}' if k == 0 else ''
            ps = posicion(ws[0][1]) if posicion else None
            if ps: pop = f'{{\\an5\\pos({ps[0]},{ps[1]})\\fs{ps[2]}}}' + pop
            ev.append(f'Dialogue: 0,{ts(t0)},{ts(t1)},Cap,,0,0,0,,{pop}{txt}')
    open(ass, 'w').write('[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\n'
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, '
        'ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
        f'Style: Cap,Inter,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,7,4,2,60,60,{SUB_MARGEN},1\n\n'
        '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n' + '\n'.join(ev) + '\n')


SUB_MARGEN = 300  # distancia del subtítulo al borde de abajo (fuera de la zona que tapa Instagram)


def subtitulos_avatar(g, video, ass, posicion):
    """Reparte las frases del guion de avatar en los tramos hablados del video de HeyGen (por pausas y sílabas)."""
    D = dur(video)
    r = subprocess.run(['ffmpeg', '-i', video, '-vn', '-af', 'silencedetect=n=-35dB:d=0.2', '-f', 'null', '-'], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', r)]; en = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', r)]
    hab, x = [], 0.0
    for a, b in zip(st, en + [D]):
        if a - x > 0.08: hab.append((x, a))
        x = b
    if D - x > 0.08: hab.append((x, D))
    if not hab: return False
    frases = [mostrar(f) for f in g.get('frases', [])]
    if not frases: return False
    sil_f = [sum(silabas(w) for w in f.split()) for f in frases]
    if len(hab) == len(frases): tr = hab
    else:  # junta o parte tramos: cada frase termina en la pausa más cercana a su parte proporcional de sílabas
        t0, t1 = hab[0][0], hab[-1][1]; hablado = sum(b - a for a, b in hab); tot = sum(sil_f)
        def en_t(h):  # segundo de habla h → tiempo real
            for a, b in hab:
                if h <= b - a: return a + h
                h -= b - a
            return t1
        cortes = [0.0]; acc = 0
        for sf in sil_f[:-1]:
            acc += sf; t = en_t(hablado * acc / tot)
            pausas = [(b0 + a1) / 2 for (_, b0), (a1, _) in zip(hab, hab[1:])]
            cerca = min(pausas, key=lambda p: abs(p - t)) if pausas else t
            cortes.append(cerca if abs(cerca - t) < 0.6 else t)
        tr = []
        for i in range(len(frases)):
            a = t0 if i == 0 else cortes[i]; b = t1 if i == len(frases) - 1 else cortes[i + 1]
            ab = [h for h in hab if h[1] > a and h[0] < b]
            tr.append((max(a, ab[0][0]) if ab else a, min(b, ab[-1][1]) if ab else b))
    palabras, gr = [], 0
    for (a, b), f in zip(tr, frases):
        ws = f.split(); pes = [silabas(w) for w in ws]; T = sum(pes); x = a; n = 0
        for w, p in zip(ws, pes):
            d = (b - a) * p / T; palabras.append((w, x, x + d, gr, D)); x += d; n += 1
            if n == 3 or w[-1] in ',.:;?!': gr += 1; n = 0
        if n: gr += 1
    escribir_ass(palabras, ass, posicion); return True


def con_subtitulos(g, out, posicion):
    """Quema los subtítulos en el video de avatar ya armado."""
    ass = out[:-4] + '.ass'
    if not subtitulos_avatar(g, out, ass, posicion): return
    tmp = out[:-4] + '.sub.mp4'
    sh('ffmpeg', '-y', '-v', 'error', '-i', out, '-vf', f'ass={ass}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
       '-c:a', 'copy', '-movflags', '+faststart', tmp)
    os.replace(tmp, out); os.remove(ass)


def brillo(out):
    """Franja de luz suave y diagonal que cruza la pantalla."""
    if os.path.exists(out): return out
    from PIL import Image
    import math
    w, h = 420, 2700
    im = Image.new('RGBA', (w, h), (255, 255, 255, 0)); px = im.load()
    for x in range(w):
        al = int(24 * math.exp(-((x - w / 2) / (w / 5)) ** 2))
        for y in range(h): px[x, y] = (255, 255, 255, al)
    im.rotate(18, expand=True, resample=Image.BICUBIC).save(out); return out


def efectos(ini, D, out):
    """Whoosh en cada cambio de escena, pop al entrar y ding en el cierre."""
    S = f'{A}/sfx'; os.makedirs(S, exist_ok=True)
    base = {'whoosh': ['-f', 'lavfi', '-i', 'anoisesrc=d=0.55:c=pink:a=0.6', '-af', 'highpass=f=300,lowpass=f=4000,afade=t=in:d=0.3:curve=exp,afade=t=out:st=0.3:d=0.25,volume=0.5'],
            'pop': ['-f', 'lavfi', '-i', 'sine=f=880:d=0.09', '-af', 'afade=t=out:d=0.09:curve=exp,volume=0.5'],
            'ding': ['-f', 'lavfi', '-i', 'sine=f=1318:d=0.7', '-af', 'afade=t=out:d=0.7:curve=exp,volume=0.45']}
    for k, a in base.items():
        if not os.path.exists(f'{S}/{k}.wav'): sh('ffmpeg', '-y', '-v', 'error', *a, '-ar', '44100', '-ac', '2', f'{S}/{k}.wav')
    E = []
    for i, (t, _, _) in enumerate(ini):
        if i: E += [('whoosh', max(0, t - 0.2)), ('pop', t + 0.05)]
    E.append(('ding', ini[-1][0] + 0.1))
    args, f = [], ''
    for j, (k, t) in enumerate(E):
        args += ['-i', f'{S}/{k}.wav']; ms = int(t * 1000); f += f'[{j}]adelay={ms}|{ms}[s{j}];'
    f += ''.join(f'[s{j}]' for j in range(len(E))) + f'amix=inputs={len(E)}:normalize=0,volume=0.55,apad=whole_dur={D},atrim=0:{D}[o]'
    sh('ffmpeg', '-y', '-v', 'error', *args, '-filter_complex', f, '-map', '[o]', '-ar', '44100', out)


def telefono(cap, salida, ancho=360, giro=0):
    """Captura real de la app dentro de un celular (bisel, esquinas redondeadas y sombra), PNG con transparencia."""
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.open(cap).convert('RGB'); b = 18
    w = ancho - 2 * b; h = round(im.height * w / im.width)
    im = im.resize((w, h), Image.LANCZOS)
    W, H, pad = ancho, h + 2 * b, 40
    lienzo = Image.new('RGBA', (W + 2 * pad, H + 2 * pad), (0, 0, 0, 0))
    sombra = Image.new('L', lienzo.size, 0)
    ImageDraw.Draw(sombra).rounded_rectangle((pad, pad + 12, pad + W, pad + H + 12), 64, fill=150)
    lienzo.putalpha(sombra.filter(ImageFilter.GaussianBlur(18)))
    cuerpo = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(cuerpo).rounded_rectangle((0, 0, W - 1, H - 1), 64, fill=(18, 18, 20, 255))
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), 48, fill=255)
    cuerpo.paste(im, (b, b), m)
    lienzo.alpha_composite(cuerpo, (pad, pad))
    if giro: lienzo = lienzo.rotate(giro, resample=Image.BICUBIC, expand=True)
    lienzo.save(salida)


def marco_telefono(salida, W=680, H=1425, b=20):
    """Bisel de celular con la pantalla transparente (para poner encima de un video)."""
    from PIL import Image, ImageDraw
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, W - 1, H - 1), 70, fill=(14, 14, 18, 255))
    hueco = Image.new('L', (W, H), 0); ImageDraw.Draw(hueco).rounded_rectangle((b, b, W - b - 1, H - b - 1), 52, fill=255)
    im.putalpha(Image.composite(Image.new('L', (W, H), 0), im.getchannel('A'), hueco))  # pantalla transparente
    ImageDraw.Draw(im).rounded_rectangle((W // 2 - 70, b + 14, W // 2 + 70, b + 44), 15, fill=(0, 0, 0, 255))  # bocina/cámara
    im.save(salida)


def circulo(salida, d=330, borde=10):
    """Máscara circular (L) y aro blanco (RGBA) para la cara pequeña."""
    from PIL import Image, ImageDraw
    m = Image.new('L', (d, d), 0); ImageDraw.Draw(m).ellipse((0, 0, d - 1, d - 1), fill=255); m.save(salida + '_m.png')
    a = Image.new('RGBA', (d + 2 * borde, d + 2 * borde), (0, 0, 0, 0))
    ImageDraw.Draw(a).ellipse((0, 0, d + 2 * borde - 1, d + 2 * borde - 1), outline=(255, 255, 255, 255), width=borde)
    a.save(salida + '_a.png')


def avatar_grande(g, src, out, tmp):
    """Estilo "grande": en las explicaciones el celular ocupa casi toda la pantalla (con la app en movimiento)
    y la cara del avatar habla en un círculo chico; en el gancho se ve el avatar completo."""
    os.makedirs(tmp, exist_ok=True)
    D = dur(src); caps = g.get('capturas', [])
    cx, cy, r = g.get('cara', [540, 520, 250])          # cara en el cuadro 1080x1920
    SW, SH, PX, PY = 600, 1298, 220, 490                 # pantalla y posición del celular
    FD, FX, FY = 360, 40, 90                             # círculo de la cara
    marco_telefono(f'{tmp}/marco.png', SW + 40, SH + 40); circulo(f'{tmp}/c', FD)
    giro = GIROS[g['giro']]
    ent = ['-loop', '1', '-t', str(D), '-i', f'{tmp}/marco.png', '-loop', '1', '-t', str(D), '-i', f'{tmp}/c_m.png',
           '-loop', '1', '-t', str(D), '-i', f'{tmp}/c_a.png']
    fg = (f"[0:v]crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920:flags=lanczos,fps=30,format=yuv420p,split=3[full][b][f];"
          f"[b]boxblur=40:3,eq=brightness=-0.2:saturation=0.8[s0];"
          f"[f]crop={2*r}:{2*r}:{cx - r}:{cy - r},scale={FD}:{FD},format=rgba[fr];[2:v]format=gray[mk];[fr][mk]alphamerge[cara]")
    for k, c in enumerate(caps):
        a, z = c['desde'], c['hasta']; i = 4 + k
        if c.get('anim'):
            mp4 = f'{tmp}/anim{k}.mp4'
            q = urllib.parse.urlencode({'negocio': c.get('negocio', giro.get('negocio', 'Tu negocio')),
                                        'servicio': giro['servicios'][0], 'servicios': '|'.join(giro['servicios']), **c.get('q', {})})
            sh('node', f'{A}/anim/grabar.js', f'{A}/anim/{c["anim"]}.html', q, str(round(z - a, 2)), mp4)
            ent += ['-i', mp4]
            fg += f";[{i}:v]scale={SW}:{SH},setpts=PTS-STARTPTS+{a}/TB[p{k}]"
        else:
            ent += ['-loop', '1', '-t', str(D), '-i', f'{A}/giros/{giro["capturas"]}/{c["img"]}.jpg']
            fg += f";[{i}:v]scale={SW}:-1,crop={SW}:'min(ih,{SH})':0:0,pad={SW}:{SH}:0:0:white[p{k}]"
        fg += f";[s{k}][p{k}]overlay={PX + 20}:{PY + 20}:enable='between(t,{a},{z})'[s{k + 1}]"
    n = len(caps); ventanas = '+'.join(f"between(t,{c['desde']},{c['hasta']})" for c in caps) or '0'
    fg += (f";[s{n}][1:v]overlay={PX}:{PY}[t1];[t1][cara]overlay={FX + 10}:{FY + 10}[t2];[t2][3:v]overlay={FX}:{FY}[demo];"
           f"[full][demo]overlay=0:0:enable='{ventanas}'[v0];"
           "[v0]drawtext=text='Escena recreada con IA':font='DejaVu Sans':fontsize=30:fontcolor=white@0.9:box=1:boxcolor=black@0.45:"
           "boxborderw=10:x=w-tw-40:y=60[v]")
    sh('ffmpeg', '-y', '-v', 'error', '-i', src, *ent, '-filter_complex', fg, '-map', '[v]', '-map', '0:a', '-t', str(D),
       '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-movflags', '+faststart', out)


def solo_app(g, wav, out, tmp):
    """Como el estilo "grande" pero SIN avatar: portada con el gancho y luego el celular grande con la app en vivo,
    sobre un fondo animado; voz + música bajita + whoosh en cada cambio. Usa los mismos `capturas` del guion."""
    os.makedirs(tmp, exist_ok=True)
    D = dur(wav); caps = g.get('capturas', []); giro = GIROS[g['giro']]
    SW, SH, PX, PY = 600, 1298, 220, 520
    H0 = caps[0]['desde'] if caps else D
    q = urllib.parse.urlencode({'gancho': g.get('gancho_pantalla', g['gancho']), 'emoji': g.get('emoji') or giro.get('emoji', '📲'),
                                'sub': g.get('sub', 'Mira 👇'), 'hasta': H0})
    sh('node', f'{A}/anim/grabar.js', f'{A}/anim/fondo.html', q, str(round(D, 2)), f'{tmp}/fondo.mp4',
       env={**os.environ, 'ANCHO': '1080', 'ALTO': '1920'})
    marco_telefono(f'{tmp}/marco.png', SW + 40, SH + 40)
    ent = ['-i', f'{tmp}/fondo.mp4', '-loop', '1', '-t', str(D), '-i', f'{tmp}/marco.png']
    fg = '[0:v]fps=30,format=yuv420p[s0]'
    for k, c in enumerate(caps):
        a, z = c['desde'], c['hasta']; i = 2 + k
        if c.get('anim'):
            mp4 = f'{tmp}/anim{k}.mp4'
            qq = urllib.parse.urlencode({'negocio': c.get('negocio', giro.get('negocio', 'Tu negocio')),
                                         'servicio': giro['servicios'][0], 'servicios': '|'.join(giro['servicios']), **c.get('q', {})})
            sh('node', f'{A}/anim/grabar.js', f'{A}/anim/{c["anim"]}.html', qq, str(round(z - a, 2)), mp4)
            ent += ['-i', mp4]; fg += f";[{i}:v]scale={SW}:{SH},setpts=PTS-STARTPTS+{a}/TB[p{k}]"
        else:
            ent += ['-loop', '1', '-t', str(D), '-i', f'{A}/giros/{giro["capturas"]}/{c["img"]}.jpg']
            fg += f";[{i}:v]scale={SW}:-1,crop={SW}:'min(ih,{SH})':0:0,pad={SW}:{SH}:0:0:white[p{k}]"
        fg += f";[s{k}][p{k}]overlay={PX + 20}:{PY + 20}:enable='between(t,{a},{z})'[s{k + 1}]"
    n = len(caps); ven = '+'.join(f"between(t,{c['desde']},{c['hasta']})" for c in caps) or '0'
    # el celular entra deslizándose desde abajo al terminar el gancho
    y = f"if(lt(t,{H0}+0.35),{PY}+(H-{PY})*(1-(t-{H0})/0.35),{PY})"
    fg += f";[s{n}][1:v]overlay={PX}:{PY}:enable='{ven}'[v]"
    if caps:  # deslizar: pantalla y marco juntos durante la entrada
        fg = fg.replace(f"overlay={PX + 20}:{PY + 20}:enable='between(t,{caps[0]['desde']},", f"overlay={PX + 20}:'{y}+20':enable='between(t,{caps[0]['desde']},", 1)
        fg = fg.replace(f"[s{n}][1:v]overlay={PX}:{PY}:", f"[s{n}][1:v]overlay={PX}:'{y}':")
    # audio: voz + música bajita + whoosh/pop en cada cambio + ding al final
    efectos([(0, 0, 0)] + [(c['desde'], 0, 0) for c in caps], D, f'{tmp}/sfx.wav')
    ent += ['-i', wav, '-stream_loop', '-1', '-i', f'{A}/musica.wav', '-i', f'{tmp}/sfx.wav']
    v, m, s = 2 + n, 3 + n, 4 + n
    fg += (f";[{v}:a]aresample=44100,volume=1.0[va];[{m}:a]aresample=44100,volume=0.10,atrim=0:{D},afade=t=out:st={max(0, D - 1.5)}:d=1.5[ma];"
           f"[{s}:a]aresample=44100[sa];[va][ma][sa]amix=inputs=3:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5[a]")
    sh('ffmpeg', '-y', '-v', 'error', *ent, '-filter_complex', fg, '-map', '[v]', '-map', '[a]', '-t', str(D),
       '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac', '-b:a', '160k', '-ar', '44100', '-movflags', '+faststart', out)


def hacer_app(ruta):
    """Videos "app en vivo" (sin avatar): `python3 fabrica.py app guiones/<archivo>.json`.
    Cada guion: id, giro, voz, gancho, gancho_pantalla, sub, emoji, texto, frases, pantallas (como los de avatar) y opcionales
    negocio, servicio (lo que pide el cliente en el chat), situaciones ("emoji|hora|texto;…" una por frase de autochat
    antes de la última), premio (tarjeta de lealtad). Deja salida/<fecha>-<id>.mp4 + .json + .jpg para `publicar`."""
    sys.path[:0] = [R, f'{R}/tts']
    import kok, avatar_ia
    hoy = datetime.date.today().isoformat(); os.makedirs(f'{R}/salida', exist_ok=True)
    for g in json.load(open(ruta)):
        vid = g['id'] if g['id'][:4].isdigit() else f"{hoy}-{g['id']}"
        T = f'{R}/trabajo/app/{vid}'; os.makedirs(T, exist_ok=True); partes, marcas, t = [], [], 0.0
        for i, x in enumerate(g['frases']):
            raw, o = f'{T}/{i}.raw.wav', f'{T}/{i}.wav'
            kok.guardar(kok.decir(x, g.get('voz', 'alex_grave'), float(g.get('velocidad', 1.08))), raw)
            sh('ffmpeg', '-y', '-v', 'error', '-i', raw, '-af', FILTRO_VOZ + ',apad=pad_dur=0.35', '-ar', '44100', '-ac', '1', o)
            partes.append(o); marcas.append(round(t, 2)); t += dur(o)
        open(f'{T}/l.txt', 'w').write('\n'.join(f"file '{x}'" for x in partes))
        sh('ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', f'{T}/l.txt', f'{T}/voz.wav')
        caps = avatar_ia.pantallas_a_capturas(g['pantallas'], marcas, round(t, 2), g['giro'])
        for c in caps:
            if g.get('negocio'): c['negocio'] = g['negocio']
            q = c.setdefault('q', {}) if c.get('anim') else {}
            if c.get('anim') == 'autochat':
                if g.get('servicio'): q['servicio'] = g['servicio']
                if g.get('situaciones') and q.get('cortes'):
                    cs = [float(x) for x in q['cortes'].split(',')]; q['situaciones'] = g['situaciones']
                    q['msg'] = round(cs[-1] + .55 * (q['p1'] - cs[-1]), 2)
            if c.get('anim') == 'lealtad' and g.get('premio'): q['premio'] = g['premio']
            if c.get('anim') == 'autoagenda':
                if g.get('pill2'): q['pill2'] = g['pill2']
                if g.get('emoji_servicio'): q['emoji'] = g['emoji_servicio']
        g['capturas'] = caps
        out = f'{R}/salida/{vid}.mp4'
        solo_app(g, f'{T}/voz.wav', out, f'{T}/r')
        ven = [(c['desde'], c['hasta']) for c in caps]; H0 = ven[0][0] if ven else 99
        pos = lambda x: (540, -600, 64) if x < H0 - .05 else ((540, 300, 64) if any(a <= x + .05 < b for a, b in ven) else None)
        ass = f'{T}/sub.ass'; subtitulos_avatar(g, f'{T}/voz.wav', ass, pos)   # tiempos de la voz limpia (sin música)
        sh('ffmpeg', '-y', '-v', 'error', '-i', out, '-vf', f'ass={ass}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
           '-c:a', 'copy', '-movflags', '+faststart', f'{T}/s.mp4'); os.replace(f'{T}/s.mp4', out)
        sh('ffmpeg', '-y', '-v', 'error', '-i', out, '-frames:v', '1', '-q:v', '3', out[:-4] + '.jpg')  # portada = primer cuadro
        json.dump({'giro': g['giro'], 'gancho': g['gancho'], 'texto': g['texto'], 'formato': g.get('formato', 'app-en-vivo'),
                   'voz': g.get('voz', '')}, open(f'{R}/salida/{vid}.json', 'w'), ensure_ascii=False)
        print('✓', vid, round(dur(out), 1), 's', flush=True)


def avatar_mano(g, src, out):
    """Estilo normal: avatar completo y el celular con capturas aparece en sus manos."""
    caps = g.get('capturas', [])
    # "mano" (por defecto): celular al centro, abajo, un poco inclinado, como si lo sostuviera frente a ella.
    # "lado": a la derecha (para tomas muy cerradas de la cara).
    mano = g.get('telefono', 'mano') == 'mano'
    ent, filtro = [], f"[0:v]crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920:flags=lanczos,fps=30,format=yuv420p[b0]"
    for k, c in enumerate(caps):
        png = f'{R}/salida/_tel{k}.png'
        telefono(f'{A}/giros/{GIROS[g["giro"]]["capturas"]}/{c["img"]}.jpg', png,
                 *((430, -5) if mano else (360, 0))); ent += ['-loop', '1', '-i', png]
        a, z = c['desde'], c['hasta']
        # entra deslizándose desde abajo (0.3 s); si sigue otra captura pegada, ya no vuelve a entrar
        pegada = k > 0 and abs(caps[k - 1]['hasta'] - a) < 0.05
        x, yf = ("(W-w)/2+40", "H-h+150") if mano else ("W-w+20", "H-h-30")
        y = yf if pegada else f"if(lt(t,{a}+0.3),H-(H-({yf}))*(t-{a})/0.3,{yf})"
        filtro += f";[b{k}][{k + 1}:v]overlay=x={x}:y='{y}':enable='between(t,{a},{z})':shortest=1[b{k + 1}]"
    etiqueta = "drawtext=text='Escena recreada con IA':font='DejaVu Sans':fontsize=34:fontcolor=white@0.9:box=1:boxcolor=black@0.45:boxborderw=12:x=(w-tw)/2:y=150"
    filtro += f';[b{len(caps)}]{etiqueta}[v]'
    sh('ffmpeg', '-y', '-v', 'error', '-i', src, *ent, '-filter_complex', filtro, '-map', '[v]', '-map', '0:a',
       '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-movflags', '+faststart', out)
    for k in range(len(caps)): os.remove(f'{R}/salida/_tel{k}.png')


def avatares():
    """Videos de avatar IA subidos a avatar/ (nombre empieza con el número del guion en guiones-avatar/pendientes.json)."""
    P = f'{R}/guiones-avatar/pendientes.json'
    pend = json.load(open(P)) if os.path.exists(P) else []
    os.makedirs(f'{R}/salida', exist_ok=True)
    hechos = []
    for f in sorted(os.listdir(f'{R}/avatar')):
        m = re.match(r'(\d+)', f)
        if not f.lower().endswith('.mp4') or not m: continue
        g = next((x for x in pend if x['num'] == int(m.group(1))), None)
        if not g: print('✗', f, '→ no hay guion pendiente con ese número'); continue
        hoy = datetime.date.today().isoformat()
        vid = f"{hoy}-{g['id']}"; out = f'{R}/salida/{vid}.mp4'
        if g.get('estilo') == 'grande': avatar_grande(g, f'{R}/avatar/{f}', out, f'{R}/trabajo/grande/{g["num"]}')
        else: avatar_mano(g, f'{R}/avatar/{f}', out)
        ven = [(c['desde'], c['hasta']) for c in g.get('capturas', [])]
        if g.get('estilo') == 'grande':  # con celular grande: arriba a la derecha, junto a la carita
            pos = lambda t: (735, 270, 58) if any(x <= t + 0.05 < y for x, y in ven) else None
        else:  # celular en mano: arriba del celular
            pos = lambda t: (540, 1060, 66) if any(x <= t + 0.05 < y for x, y in ven) else None
        con_subtitulos(g, out, pos)
        sh('ffmpeg', '-y', '-v', 'error', '-ss', '0.5', '-i', out, '-frames:v', '1', '-q:v', '3', out[:-4] + '.jpg')
        json.dump({**{k: g[k] for k in ('giro', 'gancho', 'texto')}, 'formato': 'avatar', 'voz': 'avatar'},
                  open(f'{R}/salida/{vid}.json', 'w'), ensure_ascii=False)
        git('rm', '-q', f'avatar/{f}'); pend.remove(g); hechos.append(vid)
        for k in glob.glob(f'{R}/kit-heygen/{g["num"]}-*'): git('rm', '-rq', '--ignore-unmatch', os.path.relpath(k, R)); shutil.rmtree(k, ignore_errors=True)
        print('✓', vid, round(dur(out), 1), 's', flush=True)
    if hechos:
        json.dump(pend, open(P, 'w'), ensure_ascii=False, indent=1); git('add', P)
    else:
        print('No hay videos de avatar nuevos.')


def git(*a, cwd=R):
    return subprocess.run(['git', *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


def publicar():
    S = f'{R}/salida'
    ids = sorted(f[:-5] for f in os.listdir(S) if f.endswith('.json') and os.path.exists(f'{S}/{f[:-5]}.mp4')) if os.path.isdir(S) else []
    # intercala: plantilla, avatar, plantilla, avatar… (los de avatar llevan "avatar" en el id)
    av = [i for i in ids if '-avatar-' in i]; pl = [i for i in ids if '-avatar-' not in i]
    ids = [x for par in __import__('itertools').zip_longest(pl, av) for x in par if x]
    if not ids: sys.exit('No hay videos en salida/')
    hoy = datetime.date.today().isoformat()
    cola = {'creada': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'videos': []}
    C = f'{R}/trabajo/_cola'
    shutil.rmtree(C, ignore_errors=True); os.makedirs(f'{C}/videos')
    hist_f = f'{R}/historial.json'
    hist = json.load(open(hist_f)) if os.path.exists(hist_f) else []
    for i in ids:
        m = json.load(open(f'{S}/{i}.json'))
        shutil.copy(f'{S}/{i}.mp4', f'{C}/videos/{i}.mp4')
        item = {'id': i, 'video': f'videos/{i}.mp4', 'texto': m['texto'], 'giro': m['giro'], 'gancho': m['gancho'], 'historia': True,
                'tipo': 'avatar' if '-avatar-' in i else 'plantilla'}
        if os.path.exists(f'{S}/{i}.jpg'):
            shutil.copy(f'{S}/{i}.jpg', f'{C}/videos/{i}.jpg'); item['portada'] = f'videos/{i}.jpg'
        cola['videos'].append(item)
        if not any(h['id'] == i for h in hist):
            hist.append({'id': i, 'fecha': hoy, 'giro': m['giro'], 'gancho': m['gancho'], 'formato': m.get('formato', ''), 'voz': m.get('voz', '')})
    json.dump(cola, open(f'{C}/cola.json', 'w'), ensure_ascii=False, indent=1)
    # Rama "cola": solo el lote de hoy, sin historia (no crece)
    remoto = git('remote', 'get-url', 'origin').strip()
    git('init', '-q', '-b', 'cola', cwd=C)
    git('-c', 'user.name=Fabrica Confirmapp', '-c', 'user.email=noreply@anthropic.com', 'add', '.', cwd=C)
    git('-c', 'user.name=Fabrica Confirmapp', '-c', 'user.email=noreply@anthropic.com', 'commit', '-qm', f'Cola {hoy}', cwd=C)
    git('push', '-f', remoto, 'cola', cwd=C)
    # Historial en main
    json.dump(hist, open(hist_f, 'w'), ensure_ascii=False, indent=1)
    git('add', '-A', 'historial.json', 'guiones', 'guiones-avatar', 'avatar')
    if git('status', '--porcelain').strip():
        git('-c', 'user.name=Fabrica Confirmapp', '-c', 'user.email=noreply@anthropic.com', 'commit', '-qm', f'Videos {hoy}')
    git('-c', 'push.negotiate=true', 'push', 'origin', 'HEAD:main')
    for i in ids:
        for ext in ('mp4', 'json', 'jpg'):
            if os.path.exists(f'{S}/{i}.{ext}'): os.remove(f'{S}/{i}.{ext}')
    print('Publicados en la cola:', ', '.join(ids))


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'hacer': hacer(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == 'publicar': publicar()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'avatares': avatares()
    elif len(sys.argv) >= 3 and sys.argv[1] == 'app': hacer_app(sys.argv[2])
    else: print(__doc__)
