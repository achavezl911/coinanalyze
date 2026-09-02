"""K31 · reparte las huerfanas en tres cubos DERIVADOS. Lee el JSON de probe.js por stdin.

POR QUE NO HAY NI UNA LISTA TECLEADA, y es la condicion que pidio Alejandro: una lista a
mano envejece sin avisar y convierte el check en una opinion fechada. Aqui todo sale del
arbol o de la sonda.

  fuente     una ruta que el panel PIDE y que LLEGA por mutacion. Sale de probe.js, no de
             aqui. Antes yo usaba {desk/state, dashboard/state} a mano; el criterio bueno
             es "cualquier ruta cuyo dato ya se ve", y eso lo dice el instrumento.
  productora nombre que api.py importa de app.*, mas los definidos en api.py que no son
             handlers -latest_snapshot vive ahi-, MENOS los que llama mas de un cuarto de
             los handlers. Esa ultima resta es genericidad DERIVADA DE LA FRECUENCIA:
             validate_symbol() esta en casi todos y sin quitarlo colapsaba los 27 en un
             solo cubo. Es lo unico con umbral, y va dicho en la salida.

  BUNDLE  la huerfana DEVUELVE -por su return- una productora que tambien devuelve una
          fuente. El dato ya llega a la pantalla por otra puerta.
          MIRAR EL return Y NO LA LLAMADA NO ES UN DETALLE: /api/scalp/alerts llama a
          compute_scalp_summary() y despues construye otra cosa; su return (api.py:1549)
          es {"symbol", "alerts"} y el bundle publica el SUMMARY, no las alertas. Con el
          criterio de "llama a" salia BUNDLE, y es falso: sus alertas no las lee nadie.
  DISENO  su productora se llama desde app/ fuera de api.py. Se publica QUIEN: 'IA' si es
          ai_context.py, 'interno' si no -load_baselines son 4 llamadas en scalp_logic.py
          y 0 en la IA, y eso es otra cosa que servir al modelo-.
  HUECO   ninguna de las dos. Se calcula y no la consume NADIE.
"""
import ast
import json
import pathlib
import sys
from collections import Counter

REPO = pathlib.Path(__import__('os').environ.get('REPO', '/srv/coinanalyze/repo'))
API = REPO / 'app/api.py'


def llamada(n):
    while isinstance(n, ast.Await):
        n = n.value
    if isinstance(n, ast.Call):
        f = n.func
        return f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
    return None


def var2prod(fn, dominio):
    """variable -> productora que la produjo. Y aparte, variable -> dict literal, porque
    el bundle NO devuelve sus productoras al primer nivel: desk/state hace
    'components': componentes, y componentes es un dict {clave: variable}. Sin bajar ese
    escalon, /api/hypothesis y /api/profile salian fuera del bundle, que es justo lo
    contrario de lo medido: su dato llega a la pantalla dentro de components."""
    m, dicts = {}, {}
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            c = llamada(n.value)
            if c and c in dominio:
                m[n.targets[0].id] = c
            elif isinstance(n.value, ast.Dict):
                dicts[n.targets[0].id] = n.value
    return m, dicts


def devueltas(fn, dominio):
    """Productoras que el handler DEVUELVE, en las dos formas que usa api.py:
       'return await productora(...)' y 'return {clave: productora(...)}'."""
    if not fn:
        return set()
    v2p, dicts = var2prod(fn, dominio)
    out = set()

    def del_dict(d, prof=0):
        if prof > 3:
            return
        for _k, v in zip(d.keys, d.values):
            if isinstance(v, ast.Name):
                if v.id in v2p:
                    out.add(v2p[v.id])
                elif v.id in dicts:
                    del_dict(dicts[v.id], prof + 1)
            elif isinstance(v, ast.Dict):
                del_dict(v, prof + 1)
            else:
                c = llamada(v)
                if c and c in dominio:
                    out.add(c)

    for n in ast.walk(fn):
        if not isinstance(n, ast.Return) or n.value is None:
            continue
        d = llamada(n.value)
        if d and d in dominio:
            out.add(d)
        if isinstance(n.value, ast.Dict):
            del_dict(n.value)
        elif isinstance(n.value, ast.Name):
            # 'return result' con result = await productora(...). Faltaba, y por eso
            # /api/snapshot -que hace exactamente eso en api.py:618-621- salia HUECO
            # cuando su dato lo publica dashboard/state en la clave "snapshot".
            if n.value.id in v2p:
                out.add(v2p[n.value.id])
            elif n.value.id in dicts:
                del_dict(dicts[n.value.id])
    return out


def main() -> int:
    sonda = json.load(sys.stdin)
    arbol = ast.parse(API.read_text(encoding='utf-8'))

    handlers, nombres_handler, locales = {}, set(), set()
    for n in ast.walk(arbol):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ruta = None
            for d in n.decorator_list:
                if (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                        and d.func.attr == 'get' and d.args
                        and isinstance(d.args[0], ast.Constant)
                        and str(d.args[0].value).startswith('/api/')):
                    ruta = str(d.args[0].value)
            if ruta:
                handlers[ruta] = n
                nombres_handler.add(n.name)
            else:
                locales.add(n.name)

    dominio = set(locales)
    for n in ast.walk(arbol):
        if isinstance(n, ast.ImportFrom) and (n.module or '').startswith('app.'):
            for al in n.names:
                dominio.add(al.asname or al.name)
    dominio -= nombres_handler
    # Los _privados no son productoras de dato: _utc_iso() es formato de fecha, y sin esta
    # linea /api/signals/ledger y /api/signals/outcomes "devolvian" una productora y se
    # escapaban de HUECO. Es convencion del lenguaje, no una lista teclada.
    dominio = {d for d in dominio if not d.startswith('_')}

    freq = Counter()
    for fn in handlers.values():
        for c in {c for c in (llamada(x) for x in ast.walk(fn)) if c}:
            freq[c] += 1
    umbral = max(2, len(handlers) // 4)
    dominio -= {c for c, k in freq.items() if k > umbral}

    pedidas = set(sonda.get('rutas_pedidas', []))
    llegan = set(sonda.get('llegan_a_la_pantalla', []))
    fuentes = pedidas & llegan
    prod_fuente = set()
    for r in fuentes:
        prod_fuente |= devueltas(handlers.get(r), dominio)

    consumo = {}
    for py in sorted((REPO / 'app').glob('*.py')):
        if py.name == 'api.py':
            continue
        try:
            t = ast.parse(py.read_text(encoding='utf-8'))
        except SyntaxError:
            continue
        for n in ast.walk(t):
            c = llamada(n)
            if c and c in dominio:
                consumo.setdefault(c, set()).add(py.name)

    huerfanas = sorted(sys.argv[1].split()) if len(sys.argv) > 1 else []
    cubos = {'bundle': [], 'diseno': [], 'hueco': []}
    quien = {}
    for r in huerfanas:
        fn = handlers.get(r)
        if devueltas(fn, dominio) & prod_fuente:
            cubos['bundle'].append(r)
            continue
        # POR EL return TAMBIEN AQUI, y no por "a quien llama": los dos cubos tienen que
        # preguntar lo mismo -que SIRVE esta ruta-, o el reparto es incoherente.
        # /api/scalp/alerts llama a compute_scalp_summary(), que la IA si consume, y con el
        # criterio de "llama a" salia DISENO; pero lo que DEVUELVE (api.py:1549) son sus
        # alertas, y esas no las consume nadie. Va a HUECO, que es lo medido.
        usada = {p for p in devueltas(fn, dominio) if p in consumo}
        if usada:
            cubos['diseno'].append(r)
            mods = set().union(*(consumo[p] for p in usada))
            quien[r] = 'IA' if 'ai_context.py' in mods else 'interno'
        else:
            cubos['hueco'].append(r)

    print('bundle=%d diseno=%d hueco=%d umbral_generico=%d' % (
        len(cubos['bundle']), len(cubos['diseno']), len(cubos['hueco']), umbral))
    print('BUNDLE:' + ''.join(' ' + r for r in cubos['bundle']))
    print('DISENO:' + ''.join(' %s(%s)' % (r, quien[r]) for r in cubos['diseno']))
    print('HUECO:' + ''.join(' ' + r for r in cubos['hueco']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
