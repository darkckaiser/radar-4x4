"""Rastreador de todoterrenos baratos. Se ejecuta en GitHub Actions cada 15 min."""
import json, math, os, re, time, unicodedata
from datetime import datetime, timezone, timedelta
import requests

# ---------- AJUSTES (edita aquí) ----------
MAX_PRECIO = 5000
MIN_PRECIO = 800          # descarta piezas, señales y anuncios trampa
MAX_KM = 200000
ORIGEN = (43.3614, -5.8494)   # Oviedo
MODELOS = [
    "land cruiser", "toyota hdj", "toyota kzj", "nissan patrol", "suzuki vitara",
    "suzuki jimny", "suzuki samurai", "land rover defender", "land rover discovery",
    "mitsubishi montero", "mitsubishi pajero", "santana aníbal", "santana 300",
    "jeep wrangler", "jeep cherokee", "isuzu trooper", "daihatsu feroza",
    "nissan terrano", "lada niva", "uaz", "range rover clasico", "toyota fj",
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


def wallapop(modelo):
    r = requests.get(
        "https://api.wallapop.com/api/v3/search",
        params={"keywords": modelo, "category_id": "100", "max_sale_price": MAX_PRECIO,
                "latitude": ORIGEN[0], "longitude": ORIGEN[1], "order_by": "newest",
                "source": "search_box"},
        headers={"User-Agent": UA, "X-DeviceOS": "0", "Accept": "application/json"},
        timeout=25)
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


def dist_provincia(cp=None, nombre=None):
    reg = None
    if cp and re.match(r"\d{5}", str(cp)):
        reg = PROVINCIAS.get(str(cp)[:2])
    elif nombre:
        n = sin_acentos(nombre)
        reg = next((v for v in PROVINCIAS.values() if v[0] in n or n in v[0]), None)
    return round(haversine(ORIGEN, reg[1:])) if reg else None


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


def autoscout24(paginas=5):
    out = []
    for p in range(1, paginas + 1):
        r = requests.get("https://www.autoscout24.es/lst", headers=HTML_H, timeout=30,
                         params={"priceto": MAX_PRECIO, "sort": "age", "desc": 1, "page": p})
        r.raise_for_status()
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
        items = (json.loads(m.group(1))["props"]["pageProps"].get("listings") or []) if m else []
        if not items:
            break
        for it in items:
            veh, loc = it.get("vehicle") or {}, it.get("location") or {}
            km = None
            for d in it.get("vehicleDetails") or []:
                if "kilomet" in (d.get("ariaLabel") or "").lower():
                    km = numero(d.get("data"))
            url = it.get("url") or ""
            url = "https://www.autoscout24.es" + url if url.startswith("/") else url
            titulo = " ".join(x for x in (it.get("title"), veh.get("modelVersionInput")) if x)
            out.append({"id": f"autoscout24:{it.get('id')}", "fuente": "AutoScout24", "titulo": titulo.strip(),
                        "descripcion": "", "precio": numero(it.get("price")), "km": int(km) if km else None,
                        "ciudad": loc.get("city") or "", "dist_km": dist_provincia(cp=loc.get("zip") or loc.get("zipCode")),
                        "foto": (it.get("images") or [None])[0], "url": url})
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
        r = requests.get("https://www.coches.net/segunda-mano/", headers=HTML_H, timeout=30,
                         params={"MaxPrice": MAX_PRECIO, "pg": p})
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
                        "foto": foto, "url": url})
        time.sleep(1.5)
    return out

FUENTES = {"Wallapop": wallapop}          # se consultan una vez por modelo
LISTADOS = {"AutoScout24": autoscout24, "Coches.net": cochesnet}   # últimos anuncios <= precio, se filtran por modelo


def valido(a):
    if a["precio"] is None or not (MIN_PRECIO <= a["precio"] <= MAX_PRECIO):
        return False
    texto = (a["titulo"] + " " + a["descripcion"]).lower()
    if any(x in texto for x in EXCLUIR):
        return False
    t = a["titulo"].lower()
    if a.get("_modelo"):
        if a["_modelo"].split()[-1] not in t and a["_modelo"] not in texto:
            return False
    elif not any(re.search(p, t) for p in PATRONES):
        return False
    if not a.get("km"):
        a["km"] = extraer_km(texto)
    return a["km"] is None or a["km"] <= MAX_KM


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
    previas = {a["fuente"] for a in prev["listings"]}
    nuevos = []

    def procesar(items):
        for a in items:
            if not valido(a):
                continue
            a.pop("_modelo", None)
            a["ultima_vez"] = ahora.isoformat()
            if a["id"] in conocidos:
                conocidos[a["id"]].update({k: a[k] for k in ("precio", "ultima_vez", "foto")})
            else:
                a["primera_vez"] = ahora.isoformat()
                conocidos[a["id"]] = a
                nuevos.append(a)

    tareas = [(n, f, m) for n, f in FUENTES.items() for m in MODELOS] + [(n, f, None) for n, f in LISTADOS.items()]
    for nombre, fn, modelo in tareas:
        try:
            procesar(fn(modelo) if modelo else fn())
        except Exception as e:
            print(f"[{nombre}] fallo{' con ' + repr(modelo) if modelo else ''}: {e}")
        time.sleep(1.5)

    limite = (ahora - timedelta(days=10)).isoformat()
    lista = [a for a in conocidos.values() if a["ultima_vez"] >= limite]
    lista.sort(key=lambda a: (a.get("dist_km") is None, a.get("dist_km") or 0))
    os.makedirs("data", exist_ok=True)
    json.dump({"actualizado": ahora.isoformat(), "listings": lista},
              open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    por_fuente = {f: sum(1 for a in lista if a["fuente"] == f) for f in {a["fuente"] for a in lista}}
    print(f"{len(lista)} anuncios ({por_fuente}), {len(nuevos)} nuevos")

    cerca = lambda a: (a.get("dist_km") is None, a.get("dist_km") or 0)
    nuevos.sort(key=cerca)
    for f in sorted({a["fuente"] for a in nuevos} - previas):   # fuente recién añadida: resumen, sin inundar
        n = [a for a in nuevos if a["fuente"] == f]
        telegram(f"✅ {f} añadido: {len(n)} anuncios guardados. Te muestro los 3 más cercanos; "
                 "a partir de ahora solo aviso de los nuevos.")
        for a in n[:3]:
            telegram(formato(a))
    avisar = [a for a in nuevos if a["fuente"] in previas]
    for a in avisar[:12]:
        telegram(formato(a))
    if len(avisar) > 12:
        telegram(f"…y {len(avisar) - 12} anuncios nuevos más en la app.")


if __name__ == "__main__":
    main()
