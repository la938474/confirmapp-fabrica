"""Fábrica de videos Confirmapp.

  python3 fabrica.py hacer guiones/AAAA-MM-DD.json   → valida y arma los videos en salida/
  python3 fabrica.py avatares                        → toma los .mp4 de avatar/, los prepara y los deja en salida/
  python3 fabrica.py publicar                        → sube salida/ a la rama "cola" (Supabase la importa sola)
                                                       y anota los ganchos en historial.json
"""
import glob, json, os, re, shutil, subprocess, sys, datetime

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
        render(d, len(E), f'{R}/salida/{v["id"]}.mp4', float(v.get('zoom', 0.09)))
        json.dump({k: v[k] for k in ('id', 'giro', 'gancho', 'texto')} | {'formato': v.get('formato', ''), 'voz': voz},
                  open(f'{R}/salida/{v["id"]}.json', 'w'), ensure_ascii=False)
        print('✓', v['id'], round(dur(f'{R}/salida/{v["id"]}.mp4'), 1), 's', flush=True)


def render(d, n, salida, zoom):
    vs, aus = [], []
    for i in range(n):
        a = dur(f'{d}/audio/{i}.wav')
        ex = 1.6 if i == n - 1 else 0.3
        N = int(round((a + ex) * 30)); D = N / 30
        tmp = f'{d}/esc/tmp_{i}.mp4'
        sh('ffmpeg', '-y', '-v', 'error', '-i', f'{d}/img/{i}.jpg', '-vf',
           f"zoompan=z='1+{zoom}*on/{N}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={N}:s=1080x1920:fps=30,format=yuv420p,"
           + (f"fade=in:st=0:d=0.15," if i else "") + f"fade=out:st={round(D - 0.15, 3)}:d=0.15",  # escena 0 sin fundido: el primer cuadro es la portada
           '-frames:v', str(N), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p', tmp)
        os.rename(tmp, f'{d}/esc/{i}.mp4')
        sh('ffmpeg', '-y', '-v', 'error', '-i', f'{d}/audio/{i}.wav', '-af', f'adelay=200|200,apad=whole_dur={D}', '-ar', '44100', '-ac', '2', f'{d}/esc/{i}.wav')
        vs.append(f"file '{i}.mp4'"); aus.append(f"file '{i}.wav'")
    open(f'{d}/esc/v.txt', 'w').write('\n'.join(vs)); open(f'{d}/esc/a.txt', 'w').write('\n'.join(aus))
    sh('ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', f'{d}/esc/v.txt', '-c', 'copy', f'{d}/esc/v.mp4')
    sh('ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', f'{d}/esc/a.txt', '-c:a', 'pcm_s16le', f'{d}/esc/voz.wav')
    D = dur(f'{d}/esc/v.mp4')
    sh('ffmpeg', '-y', '-v', 'error', '-i', f'{d}/esc/voz.wav', '-i', f'{A}/musica.wav', '-filter_complex',
       f"[1:a]volume=0.3,atrim=0:{D},afade=t=in:d=0.5,afade=t=out:st={D - 1.5}:d=1.5,aformat=channel_layouts=stereo[m];[0:a]asplit[v1][v2];"
       "[m][v1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[md];[md][v2]amix=inputs=2:normalize=0,alimiter=limit=0.95[o]",
       '-map', '[o]', '-ar', '44100', f'{d}/esc/mix.wav')
    tmp = salida[:-4] + '.tmp.mp4'
    sh('ffmpeg', '-y', '-v', 'error', '-i', f'{d}/esc/v.mp4', '-i', f'{d}/esc/mix.wav', '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
       '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', tmp)
    os.rename(tmp, salida)
    shutil.copy(f'{d}/img/0.jpg', salida[:-4] + '.jpg')  # portada = primera escena


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
        sh('ffmpeg', '-y', '-v', 'error', '-i', f'{R}/avatar/{f}', *ent, '-filter_complex', filtro, '-map', '[v]', '-map', '0:a',
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-movflags', '+faststart', out)
        for k in range(len(caps)): os.remove(f'{R}/salida/_tel{k}.png')
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
        item = {'id': i, 'video': f'videos/{i}.mp4', 'texto': m['texto'], 'giro': m['giro'], 'gancho': m['gancho'], 'historia': True}
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
    else: print(__doc__)
