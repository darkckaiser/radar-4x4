"""Rastreador de todoterrenos baratos. Se ejecuta en GitHub Actions cada 15 min."""
import json, math, os, re, time, unicodedata
from datetime import datetime, timezone, timedelta
import requests

# ---------- AJUSTES (edita aquí) ----------
MAX_PRECIO = 300000        # solo descarta precios absurdos (p. ej. 99999999 = 'consultar')
TRAMOS = [(0, 2500), (2500, 5000), (5000, 10000), (10000, None)]   # se consulta cada tramo por separado
MIN_PRECIO = 800          # descarta piezas, señales y anuncios trampa
MAX_KM = 200000
PRESUPUESTO_S = 540        # una vuelta nunca dura más de 9 min: guarda lo que lleve y sigue
MAX_DIAS = 365            # se descartan anuncios publicados hace más de un año
ORIGEN = (43.3614, -5.8494)   # Oviedo
MODELOS = [
    "land cruiser", "toyota hdj", "toyota kzj", "nissan patrol", "suzuki vitara",
    "suzuki jimny", "suzuki samurai", "land rover defender", "land rover discovery",
    "mitsubishi montero", "mitsubishi pajero", "santana aníbal", "santana 300",
    "jeep wrangler", "jeep cherokee", "isuzu trooper", "daihatsu feroza",
    "nissan terrano", "lada niva", "uaz", "range rover clasico", "toyota fj",
    "toyota hilux", "toyota prado", "toyota 4runner", "mercedes clase g", "nissan navara",
    "nissan pathfinder", "mitsubishi l200", "ford ranger", "isuzu d-max", "suzuki grand vitara",
    "jeep grand cherokee", "land rover freelander", "hummer", "ssangyong rexton",
]
EXCLUIR = ["recambio", "despiece", "piezas", "juguete", "maqueta", "escala 1",
           "para piezas", "sin motor", "accidentado", "averiado", "se compra", "compro"]
# ------------------------------------------

DATA = "data/listings.json"
UA = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Mobile Safari/537.36")


def haversine(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def extraer_km(texto):
    t = texto.lower().replace(".", "").replace(",", "")
    m = re.search(r"(\d{2,3})\s?mil\s?km", t)
    if m:
        return int(m.group(1)) * 1000
    m = re.search(r"(\d{4,6})\s?km", t)
    return int(m.group(1)) if m else None


IDENT = [  # patrón en el título -> (marca, modelo); el orden importa
    (r"land.?cruiser|\bhdj|\bkzj|\bkdj|toyota fj|\bprado\b", "Toyota", "Land Cruiser"),
    (r"hilux", "Toyota", "Hilux"), (r"4 ?runner", "Toyota", "4Runner"),
    (r"clase g\b|g-?wagen|g-?class|\bg ?(?:270|290|300|320|350|400|500)\b", "Mercedes-Benz", "Clase G"),
    (r"navara", "Nissan", "Navara"), (r"pathfinder", "Nissan", "Pathfinder"),
    (r"\bl-?200\b", "Mitsubishi", "L200"), (r"\branger\b", "Ford", "Ranger"), (r"d-?max", "Isuzu", "D-Max"),
    (r"grand vitara", "Suzuki", "Grand Vitara"), (r"grand cherokee", "Jeep", "Grand Cherokee"),
    (r"freelander", "Land Rover", "Freelander"), (r"hummer", "Hummer", "Hummer"), (r"rexton", "SsangYong", "Rexton"),
    (r"patrol", "Nissan", "Patrol"), (r"terrano", "Nissan", "Terrano"),
    (r"vitara", "Suzuki", "Vitara"), (r"jimny", "Suzuki", "Jimny"), (r"samurai", "Suzuki", "Samurai"),
    (r"defender", "Land Rover", "Defender"), (r"discovery", "Land Rover", "Discovery"),
    (r"range rover", "Land Rover", "Range Rover"), (r"land rover", "Land Rover", "Otro"),
    (r"montero", "Mitsubishi", "Montero"), (r"pajero", "Mitsubishi", "Pajero"),
    (r"santana", "Santana", "Santana"), (r"wrangler", "Jeep", "Wrangler"), (r"cherokee", "Jeep", "Cherokee"),
    (r"trooper", "Isuzu", "Trooper"), (r"feroza", "Daihatsu", "Feroza"),
    (r"\bniva\b", "Lada", "Niva"), (r"\buaz\b", "UAZ", "UAZ"),
]


def identificar(texto):
    t = (texto or "").lower()
    for pat, marca, modelo in IDENT:
        if re.search(pat, t):
            return marca, modelo
    return None, None


def extraer_anio(titulo, descripcion=""):
    tope = datetime.now().year + 1
    for m in re.finditer(r"\b(19[6-9]\d|20[0-3]\d)\b", titulo or ""):
        if int(m.group(1)) <= tope:
            return int(m.group(1))
    m = re.search(r"(?:año|matricul\w*|del)\s*:?\s*(19[6-9]\d|20[0-3]\d)", (descripcion or "").lower())
    return int(m.group(1)) if m and int(m.group(1)) <= tope else None


def extraer_cv(texto):
    t = (texto or "").lower()
    m = re.search(r"(\d{2,3})\s?(?:cv|hp|caballos)\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{2,3})\s?kw", t)
    return round(int(m.group(1)) * 1.36) if m else None


def a_fecha(x):
    """Convierte timestamps (s/ms) o textos ISO a ISO UTC; None si no se entiende."""
    try:
        if x is None or x == "":
            return None
        if isinstance(x, (int, float)) or str(x).isdigit():
            v = float(x)
            v = v / 1000 if v > 1e11 else v
            return datetime.fromtimestamp(v, timezone.utc).isoformat()
        d = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def entero(x):
    n = numero(x)
    return int(n) if n else None


def wallapop(modelo, tramo=(None, None)):
    r = requests.get(
        "https://api.wallapop.com/api/v3/search",
        params={"keywords": modelo, "category_id": "100",
                **({"min_sale_price": tramo[0]} if tramo[0] else {}),
                **({"max_sale_price": tramo[1]} if tramo[1] else {}),
                "latitude": ORIGEN[0], "longitude": ORIGEN[1], "order_by": "newest",
                "source": "search_box"},
        headers={"User-Agent": UA, "X-DeviceOS": "0", "Accept": "application/json"},
        timeout=15)
    r.raise_for_status()
    j = r.json()
    items = (j.get("data", {}).get("section", {}).get("payload", {}).get("items")
             or j.get("search_objects") or [])
    out = []
    for it in items:
        precio = it.get("price")
        if isinstance(precio, dict):
            precio = precio.get("amount")
        loc = it.get("location") or {}
        imgs = it.get("images") or []
        foto = None
        if imgs:
            u = imgs[0].get("urls") or imgs[0]
            foto = u.get("small") or u.get("medium") or u.get("original")
        slug = it.get("web_slug") or it.get("id")
        ta = it.get("type_attributes") or {}
        fecha = next((a_fecha(it.get(k)) for k in ("creation_date", "created_at", "publication_date") if it.get(k)), None)
        lat, lon = loc.get("latitude"), loc.get("longitude")
        out.append({
            "id": f"wallapop:{it.get('id')}",
            "fuente": "Wallapop",
            "titulo": (it.get("title") or "").strip(),
            "descripcion": (it.get("description") or "")[:400],
            "precio": float(precio) if precio is not None else None,
            "ciudad": loc.get("city") or loc.get("region") or "",
            "dist_km": round(haversine(ORIGEN, (lat, lon))) if lat and lon else None,
            "foto": foto,
            "url": f"https://es.wallapop.com/item/{slug}",
            "provincia": nombre_provincia(cp=loc.get("postal_code"), nombre=loc.get("region"), lat=lat, lon=lon),
            "fecha_pub": fecha, "anio": entero(ta.get("year")), "km": entero(ta.get("km")),
            "cv": entero(ta.get("horsepower") or ta.get("hp")),
            "_modelo": modelo,
        })
    return out


PROVINCIAS = {  # código postal (2 primeras cifras): (nombre, lat, lon)
 "01":("alava",42.85,-2.67),"02":("albacete",38.99,-1.86),"03":("alicante",38.35,-0.48),"04":("almeria",36.84,-2.46),
 "05":("avila",40.66,-4.70),"06":("badajoz",38.88,-6.97),"07":("baleares",39.57,2.65),"08":("barcelona",41.39,2.17),
 "09":("burgos",42.34,-3.70),"10":("caceres",39.47,-6.37),"11":("cadiz",36.53,-6.29),"12":("castellon",39.99,-0.04),
 "13":("ciudad real",38.99,-3.93),"14":("cordoba",37.89,-4.78),"15":("a coruna",43.37,-8.40),"16":("cuenca",40.07,-2.14),
 "17":("girona",41.98,2.82),"18":("granada",37.18,-3.60),"19":("guadalajara",40.63,-3.17),"20":("gipuzkoa",43.32,-1.98),
 "21":("huelva",37.26,-6.95),"22":("huesca",42.14,-0.41),"23":("jaen",37.78,-3.79),"24":("leon",42.60,-5.57),
 "25":("lleida",41.62,0.62),"26":("la rioja",42.47,-2.45),"27":("lugo",43.01,-7.56),"28":("madrid",40.42,-3.70),
 "29":("malaga",36.72,-4.42),"30":("murcia",37.99,-1.13),"31":("navarra",42.82,-1.64),"32":("ourense",42.34,-7.86),
 "33":("asturias",43.36,-5.85),"34":("palencia",42.01,-4.53),"35":("las palmas",28.12,-15.43),"36":("pontevedra",42.43,-8.64),
 "37":("salamanca",40.97,-5.66),"38":("santa cruz de tenerife",28.46,-16.25),"39":("cantabria",43.46,-3.81),"40":("segovia",40.95,-4.12),
 "41":("sevilla",37.39,-5.98),"42":("soria",41.76,-2.46),"43":("tarragona",41.12,1.25),"44":("teruel",40.34,-1.11),
 "45":("toledo",39.86,-4.03),"46":("valencia",39.47,-0.38),"47":("valladolid",41.65,-4.72),"48":("bizkaia",43.26,-2.93),
 "49":("zamora",41.50,-5.75),"50":("zaragoza",41.65,-0.88),"51":("ceuta",35.89,-5.32),"52":("melilla",35.29,-2.94),
}
PATRONES = [r"land.?cruiser", r"\bhdj", r"\bkzj", r"patrol", r"vitara", r"jimny", r"samurai", r"defender",
            r"land rover", r"range rover", r"montero", r"pajero", r"santana", r"wrangler", r"cherokee",
            r"trooper", r"feroza", r"terrano", r"\bniva\b", r"\buaz\b", r"toyota fj"]
HTML_H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36",
          "Accept": "text/html,application/xhtml+xml", "Accept-Language": "es-ES,es;q=0.9"}


def sin_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")


PROV_NOMBRE = {
 "01":"Álava","02":"Albacete","03":"Alicante","04":"Almería","05":"Ávila","06":"Badajoz","07":"Baleares","08":"Barcelona",
 "09":"Burgos","10":"Cáceres","11":"Cádiz","12":"Castellón","13":"Ciudad Real","14":"Córdoba","15":"A Coruña","16":"Cuenca",
 "17":"Girona","18":"Granada","19":"Guadalajara","20":"Gipuzkoa","21":"Huelva","22":"Huesca","23":"Jaén","24":"León",
 "25":"Lleida","26":"La Rioja","27":"Lugo","28":"Madrid","29":"Málaga","30":"Murcia","31":"Navarra","32":"Ourense",
 "33":"Asturias","34":"Palencia","35":"Las Palmas","36":"Pontevedra","37":"Salamanca","38":"Santa Cruz de Tenerife",
 "39":"Cantabria","40":"Segovia","41":"Sevilla","42":"Soria","43":"Tarragona","44":"Teruel","45":"Toledo","46":"Valencia",
 "47":"Valladolid","48":"Bizkaia","49":"Zamora","50":"Zaragoza","51":"Ceuta","52":"Melilla",
}
ALIAS_PROV = {"vizcaya": "48", "guipuzcoa": "20", "la coruna": "15", "coruna": "15", "alacant": "03", "castello": "12",
              "illes balears": "07", "islas baleares": "07", "gerona": "17", "lerida": "25", "orense": "32",
              "oviedo": "33", "principado de asturias": "33", "santander": "39", "navarra/nafarroa": "31",
              "valencia/valencia": "46", "alicante/alacant": "03", "castellon/castello": "12"}


def codigo_provincia(cp=None, nombre=None, lat=None, lon=None):
    """Código de provincia (01-52): por código postal, por nombre o por la capital más cercana."""
    if cp and re.match(r"\d{5}", str(cp)) and str(cp)[:2] in PROVINCIAS:
        return str(cp)[:2]
    if nombre:
        n = sin_acentos(nombre).strip()
        for c, v in PROVINCIAS.items():
            if v[0] == n:
                return c
        if n in ALIAS_PROV:
            return ALIAS_PROV[n]
        if len(n) > 3:
            for c, v in PROVINCIAS.items():
                if v[0] in n or n in v[0]:
                    return c
    if lat and lon:
        try:
            return min(PROVINCIAS, key=lambda c: haversine((float(lat), float(lon)), PROVINCIAS[c][1:]))
        except Exception:
            pass
    return None


def nombre_provincia(**k):
    return PROV_NOMBRE.get(codigo_provincia(**k) or "")


def dist_provincia(cp=None, nombre=None):
    c = codigo_provincia(cp=cp, nombre=nombre)
    return round(haversine(ORIGEN, PROVINCIAS[c][1:])) if c else None


def numero(x):
    """Extrae un número de un valor que puede ser int, texto ('€ 4.990') o dict."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, dict):
        for k in ("priceRaw", "raw", "amount", "price", "value", "priceFormatted"):
            if k in x and x[k] is not None:
                return numero(x[k])
        x = json.dumps(x)
    m = re.search(r"\d{1,3}(?:\.\d{3})+|\d+", str(x))
    return float(m.group(0).replace(".", "")) if m else None


AS24_MODELOS = ["toyota/hilux", "nissan/navara", "mitsubishi/l200", "ford/ranger", "isuzu/d-max",
                "suzuki/grand-vitara", "jeep/grand-cherokee", "land-rover/freelander", "toyota/land-cruiser", "nissan/patrol", "nissan/terrano", "suzuki/vitara", "suzuki/jimny",
                "suzuki/samurai", "land-rover/defender", "land-rover/discovery", "land-rover/range-rover",
                "mitsubishi/montero", "mitsubishi/pajero", "jeep/wrangler", "jeep/cherokee", "isuzu/trooper",
                "daihatsu/feroza", "lada/niva"]


def autoscout24():
    out, ok = [], 0
    for ruta in AS24_MODELOS:
        try:
            out += _as24(f"https://www.autoscout24.es/lst/{ruta}", {"sort": "age", "desc": 1}, 2)
            ok += 1
        except Exception as e:
            print(f"[AutoScout24] {ruta}: {e}")
        time.sleep(1.5)
    if not ok:   # si las páginas por modelo no responden, se recorren los últimos anuncios baratos en general
        out = _as24("https://www.autoscout24.es/lst", {"sort": "age", "desc": 1}, 5)
    return out


def _as24(url, params, paginas):
    out = []
    for p in range(1, paginas + 1):
        r = requests.get(url, headers=HTML_H, timeout=20, params={**params, "page": p})
        r.raise_for_status()
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
        items = (json.loads(m.group(1))["props"]["pageProps"].get("listings") or []) if m else []
        if not items:
            break
        for it in items:
            veh, loc = it.get("vehicle") or {}, it.get("location") or {}
            km = anio = cv = None
            for d in it.get("vehicleDetails") or []:
                et, dato = (d.get("ariaLabel") or "").lower(), str(d.get("data") or "")
                if "kilomet" in et:
                    km = numero(dato)
                elif "matricul" in et or "año" in et:
                    m = re.search(r"(19|20)\d\d", dato)
                    anio = int(m.group(0)) if m else None
                elif "potencia" in et:
                    cv = extraer_cv(dato)
            url = it.get("url") or ""
            url = "https://www.autoscout24.es" + url if url.startswith("/") else url
            titulo = " ".join(x for x in (it.get("title"), veh.get("modelVersionInput")) if x)
            out.append({"id": f"autoscout24:{it.get('id')}", "fuente": "AutoScout24", "titulo": titulo.strip(),
                        "descripcion": "", "precio": numero(it.get("price")), "km": int(km) if km else None,
                        "ciudad": loc.get("city") or "", "dist_km": dist_provincia(cp=loc.get("zip") or loc.get("zipCode")),
                        "foto": (it.get("images") or [None])[0], "url": url,
                        "anio": anio, "cv": cv, "fecha_pub": None,
                        "provincia": nombre_provincia(cp=loc.get("zip") or loc.get("zipCode"), nombre=loc.get("city"))})
        time.sleep(1.5)
    return out


def _listas(o, ruta="", out=None, prof=0):
    out = [] if out is None else out
    if prof > 14:
        return out
    if isinstance(o, list):
        if o and all(isinstance(x, dict) for x in o):
            out.append(o)
        for x in o[:3]:
            _listas(x, ruta, out, prof + 1)
    elif isinstance(o, dict):
        for v in o.values():
            _listas(v, ruta, out, prof + 1)
    return out


def cochesnet(paginas=3):
    out = []
    for p in range(1, paginas + 1):
        r = requests.get("https://www.coches.net/segunda-mano/", headers=HTML_H, timeout=20,
                         params={"pg": p})
        r.raise_for_status()
        i = r.text.find("window.__INITIAL_PROPS__ = JSON.parse(")
        if i < 0:
            print("[Coches.net] no encuentro los datos de la página")
            break
        texto, _ = json.JSONDecoder().raw_decode(r.text[r.text.index('"', i):])
        cand = [l for l in _listas(json.loads(texto)) if len(l) >= 3 and all("price" in x for x in l)
                and all(("url" in x or "title" in x) for x in l)]
        if not cand:
            print("[Coches.net] sin lista de anuncios reconocible; claves de la página:",
                  list(json.loads(texto).keys())[:20])
            break
        for it in max(cand, key=len):
            loc = it.get("location")
            prov = (loc.get("mainProvince") or loc.get("province") or loc.get("city")) if isinstance(loc, dict) else loc
            res = it.get("resources") or it.get("images") or []
            foto = (res[0].get("url") if res and isinstance(res[0], dict) else (res[0] if res else None)) or it.get("img")
            url = it.get("url") or ""
            url = "https://www.coches.net" + url if url.startswith("/") else url
            km = numero(it.get("km") or it.get("mileage"))
            out.append({"id": f"cochesnet:{it.get('id') or url}", "fuente": "Coches.net",
                        "titulo": (it.get("title") or "").strip(), "descripcion": "",
                        "precio": numero(it.get("price")), "km": int(km) if km else None,
                        "ciudad": prov if isinstance(prov, str) else "", "dist_km": dist_provincia(nombre=prov) if isinstance(prov, str) else None,
                        "foto": foto, "url": url, "anio": entero(it.get("year")),
                        "provincia": nombre_provincia(nombre=prov) if isinstance(prov, str) else None,
                        "cv": entero(it.get("hp") or it.get("power") or it.get("horsePower")),
                        "fecha_pub": next((a_fecha(it.get(k)) for k in ("publishedDate", "publicationDate", "creationDate", "date") if it.get(k)), None)})
        time.sleep(1.5)
    return out

LISTADOS = {"AutoScout24": autoscout24, "Coches.net": cochesnet}   # últimos anuncios <= precio, se filtran por modelo


def valido(a):
    if a["precio"] is None or not (MIN_PRECIO <= a["precio"] <= MAX_PRECIO):
        return False
    texto = (a["titulo"] + " " + a["descripcion"]).lower()
    if any(x in texto for x in EXCLUIR):
        return False
    if not identificar(a["titulo"])[0]:
        return False
    if not a.get("km"):
        a["km"] = extraer_km(texto)
    if a["km"] is not None and a["km"] > MAX_KM:
        return False
    fp = a.get("fecha_pub")
    if fp and fp < (datetime.now(timezone.utc) - timedelta(days=MAX_DIAS)).isoformat():
        return False                         # publicado hace más de un año
    a["marca"], a["modelo"] = identificar(a["titulo"])
    if not a["marca"]:
        a["marca"], a["modelo"] = identificar(a.get("_modelo", ""))
    a["anio"] = a.get("anio") or extraer_anio(a["titulo"], a.get("descripcion", ""))
    a["cv"] = a.get("cv") or extraer_cv(texto)
    a["provincia"] = a.get("provincia") or nombre_provincia(nombre=a.get("ciudad"))
    return True


def telegram(msg):
    tok, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if not (tok and chat):
        print("Telegram sin configurar:", msg[:80])
        return
    try:
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          data={"chat_id": chat, "text": msg}, timeout=20)
        if r.status_code != 200:
            print("Telegram devolvió", r.status_code, r.text[:200])
    except Exception as e:
        print("Telegram falló:", e)


def formato(a):
    km = f"{a['km']:,} km".replace(",", ".") if a.get("km") else "km sin indicar"
    d = f" · a {a['dist_km']} km de Oviedo" if a.get("dist_km") is not None else ""
    return f"🚙 {a['titulo']} [{a['fuente']}]\n{int(a['precio'])} € · {km}\n{a['ciudad']}{d}\n{a['url']}"


def main():
    ahora = datetime.now(timezone.utc)
    try:
        prev = json.load(open(DATA, encoding="utf-8"))
    except Exception:
        prev = {"listings": []}
    conocidos = {a["id"]: a for a in prev["listings"]}
    def tramo_de(p):
        return next((i for i, (lo, hi) in enumerate(TRAMOS) if p >= lo and (hi is None or p < hi)), 0)

    def clave(a):
        return (a["fuente"], tramo_de(a["precio"]))

    previas = {clave(a) for a in prev["listings"]}
    nuevos = []

    stats = {}

    def procesar(items, nombre):
        st = stats.setdefault(nombre, {"leidos": 0, "aceptados": 0})
        st["leidos"] += len(items)
        for a in items:
            if not valido(a):
                continue
            st["aceptados"] += 1
            a.pop("_modelo", None)
            a["ultima_vez"] = ahora.isoformat()
            if a["id"] in conocidos:
                conocidos[a["id"]].update({k: v for k, v in a.items() if v is not None and k != "primera_vez"})
            else:
                a["primera_vez"] = ahora.isoformat()
                conocidos[a["id"]] = a
                nuevos.append(a)

    tareas = [("Wallapop", (lambda m=m, t=t: wallapop(m, t)), f"{m} {t}") for m in MODELOS for t in TRAMOS]
    tareas += [(n, f, None) for n, f in LISTADOS.items()]
    k = int(time.time() // 600) % len(tareas)
    tareas = tareas[k:] + tareas[:k]
    inicio = time.time()
    for nombre, fn, etiqueta in tareas:
        if time.time() - inicio > PRESUPUESTO_S:
            print(f"Vuelta cortada a los {PRESUPUESTO_S} s (el portal responde lento); se guarda lo recogido.")
            break
        try:
            procesar(fn(), nombre)
        except Exception as e:
            print(f"[{nombre}] fallo{' con ' + repr(etiqueta) if etiqueta else ''}: {e}")
        time.sleep(1.0 if etiqueta else 1.5)

    limite = (ahora - timedelta(days=10)).isoformat()
    tope_pub = (ahora - timedelta(days=MAX_DIAS)).isoformat()
    lista = [a for a in conocidos.values() if a["ultima_vez"] >= limite
             and (a.get("fecha_pub") or a.get("primera_vez") or "9") >= tope_pub]
    lista.sort(key=lambda a: (a.get("dist_km") is None, a.get("dist_km") or 0))
    for a in lista:          # completa la provincia de anuncios guardados antes de existir este dato
        a["provincia"] = a.get("provincia") or nombre_provincia(nombre=a.get("ciudad"))
    os.makedirs("data", exist_ok=True)
    json.dump({"actualizado": ahora.isoformat(), "listings": lista},
              open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for n, st in stats.items():
        print(f"[{n}] anuncios leídos: {st['leidos']} · válidos tras filtros (precio, km, modelo, fecha): {st['aceptados']}")
    por_fuente = {f: sum(1 for a in lista if a["fuente"] == f) for f in {a["fuente"] for a in lista}}
    print(f"{len(lista)} anuncios ({por_fuente}), {len(nuevos)} nuevos")

    cerca = lambda a: (a.get("dist_km") is None, a.get("dist_km") or 0)
    nuevos.sort(key=cerca)
    def etiqueta_tramo(k):
        lo, hi = TRAMOS[k[1]]
        rango = f"< {hi:,}".replace(",", ".") if lo == 0 else (f"> {lo:,}".replace(",", ".") if hi is None else f"{lo:,}–{hi:,}".replace(",", "."))
        return f"{k[0]} ({rango} €)"

    for k in sorted({clave(a) for a in nuevos} - previas):   # combinación portal+precio vista por primera vez: resumen
        n = [a for a in nuevos if clave(a) == k]
        telegram(f"✅ {etiqueta_tramo(k)}: {len(n)} anuncios guardados. Te muestro los 3 más cercanos; "
                 "a partir de ahora solo aviso de los nuevos.")
        for a in n[:3]:
            telegram(formato(a))
    avisar = [a for a in nuevos if clave(a) in previas]
    for a in avisar[:12]:
        telegram(formato(a))
    if len(avisar) > 12:
        telegram(f"…y {len(avisar) - 12} anuncios nuevos más en la app.")


if __name__ == "__main__":
    main()
