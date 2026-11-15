"""Kokoro (ONNX) + fonetizador propio de español latino (sin espeak)."""
import json, re, wave, unicodedata
import numpy as np, onnxruntime as ort

import os, glob
D = os.path.dirname(os.path.abspath(__file__)) + '/'
if not os.path.exists(D + 'kokoro.onnx'):
    with open(D + 'kokoro.onnx', 'wb') as f:
        for p in sorted(glob.glob(D + 'kokoro.onnx.part*')): f.write(open(p, 'rb').read())
cfg = json.load(open(D + 'config.json'))
vocab = cfg['vocab']
sess = ort.InferenceSession(D + 'kokoro.onnx', providers=['CPUExecutionProvider'])
tin = [i.name for i in sess.get_inputs() if i.name not in ('style', 'speed')][0]
V = dict(np.load(D + 'voices.bin'))

def estilo(nombre):
    MEZ = {'dora_brillante': [('ef_dora', .72), ('af_heart', .28)], 'alex_grave': [('em_alex', .7), ('am_michael', .3)]}
    if nombre in MEZ: return sum(V[k] * w for k, w in MEZ[nombre])
    return V[nombre]

# ---------- fonética del español (es-419: seseo, yeísmo) ----------
FUERTES = set('aeoáéíóú')
ACENT = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u'}
VOC = set('aeiouáéíóúü')
ATONAS = {'el', 'la', 'los', 'las', 'de', 'del', 'y', 'e', 'o', 'u', 'en', 'que', 'tu', 'tus', 'mi', 'mis', 'se', 'te', 'me', 'le', 'les', 'lo',
          'con', 'por', 'a', 'al', 'un', 'su', 'sus', 'si', 'ni', 'nos', 'para', 'sin', 'como', 'pero', 'cuando', 'donde'}

def nucleos(w):
    """Devuelve lista de (inicio, fin) de núcleos vocálicos en la palabra (letras)."""
    res, i = [], 0
    while i < len(w):
        if w[i] in VOC:
            j = i + 1
            while j < len(w) and w[j] in VOC:
                a, b = w[j - 1], w[j]
                if a in FUERTES and b in FUERTES: break   # hiato
                j += 1
            res.append((i, j)); i = j
        else: i += 1
    return res

def palabra(w):
    w0 = w
    w = w.lower()
    if not w: return ''
    ns = nucleos(w)
    # sílaba tónica
    t = None
    for k, (a, b) in enumerate(ns):
        if any(c in ACENT for c in w[a:b]): t = k
    if t is None and ns:
        if len(ns) == 1: t = None if w in ATONAS else 0
        elif w[-1] in 'aeiouns': t = len(ns) - 2
        else: t = len(ns) - 1
    stress_pos = None
    if t is not None:
        a, b = ns[t]
        # la vocal "fuerte" o acentuada dentro del núcleo
        idx = a
        for c in range(a, b):
            if w[c] in ACENT or w[c] in 'aeo': idx = c; break
        stress_pos = idx
    out, i, n = [], 0, len(w)
    def prev_voc(i): return i > 0 and (w[i - 1] in VOC)
    while i < n:
        c = w[i]; nx = w[i + 1] if i + 1 < n else '#'; nx2 = w[i + 2] if i + 2 < n else '#'
        if i == stress_pos: out.append('ˈ')
        if c in VOC:
            v = ACENT.get(c, c)
            if c == 'ü': v = 'w'
            elif c in 'iu' and i != stress_pos:
                # semivocal antes de vocal
                if nx in VOC and not (nx in 'iu' and False): v = 'j' if c == 'i' else 'w'
            out.append(v); i += 1; continue
        if c == 'c' and nx == 'h': out.append('tʃ'); i += 2; continue
        if c == 'l' and nx == 'l': out.append('ʝ'); i += 2; continue
        if c == 'r' and nx == 'r': out.append('r'); i += 2; continue
        if c == 'q' and nx == 'u': out.append('k'); i += 2; continue
        if c == 'g' and nx == 'u' and nx2 in 'eéií': out.append('ɣ' if prev_voc(i) else 'ɡ'); i += 2; continue
        if c == 'c': out.append('s' if nx in 'eéií' else 'k'); i += 1; continue
        if c == 'g': out.append('x' if nx in 'eéií' else ('ɣ' if prev_voc(i) else 'ɡ')); i += 1; continue
        if c == 'z': out.append('s'); i += 1; continue
        if c == 'j': out.append('x'); i += 1; continue
        if c == 'h': i += 1; continue
        if c == 'ñ': out.append('ɲ'); i += 1; continue
        if c == 'y':
            out.append('ʝ' if nx in VOC else 'i'); i += 1; continue
        if c in 'bv': out.append('β' if prev_voc(i) else 'b'); i += 1; continue
        if c == 'd': out.append('ð' if prev_voc(i) and nx != '#' else ('ð' if prev_voc(i) else 'd')); i += 1; continue
        if c == 'r': out.append('r' if i == 0 or (i > 0 and w[i - 1] in 'nls') else 'ɾ'); i += 1; continue
        if c == 'x': out.append('ks'); i += 1; continue
        if c == 'n':
            out.append('m' if nx in 'bvpm' else ('ŋ' if nx in 'kgqj' else 'n')); i += 1; continue
        if c == 'w': out.append('w'); i += 1; continue
        if c.isalpha(): out.append(c); i += 1; continue
        i += 1
    return ''.join(out)

def fon(texto, _lang=None):
    t = texto.replace('¡', '').replace('¿', '').replace('—', ', ').replace('…', '.')
    t = re.sub(r'\s+', ' ', t).strip()
    partes = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+|[,.!?;:]", t)
    out = ''
    for p in partes:
        if re.match(r'[,.!?;:]', p): out = out.rstrip() + p + ' '
        else: out += palabra(p) + ' '
    out = out.strip()
    return ''.join(ch for ch in out if ch in vocab)

def decir(texto, voz='dora_brillante', speed=1.08):
    ph = fon(texto); toks = [vocab[c] for c in ph][:509]
    st = estilo(voz)[len(toks) - 1]
    a = sess.run(None, {tin: np.array([[0, *toks, 0]], dtype=np.int64), 'style': np.asarray(st, dtype=np.float32), 'speed': np.array([speed], dtype=np.float32)})[0]
    return np.asarray(a).reshape(-1)

def guardar(audio, ruta, sr=24000):
    a = np.clip(audio, -1, 1); a = (a * 32767).astype(np.int16)
    with wave.open(ruta, 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr); f.writeframes(a.tobytes())
