"""Rastreador de todoterrenos baratos. Se ejecuta en GitHub Actions cada 15 min."""
import json, math, os, re, time
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


FUENTES = {"Wallapop": wallapop}   # aquí se añadirán más portales


def valido(a):
    if a["precio"] is None or not (MIN_PRECIO <= a["precio"] <= MAX_PRECIO):
        return False
    texto = (a["titulo"] + " " + a["descripcion"]).lower()
    if any(x in texto for x in EXCLUIR):
        return False
    if a["_modelo"].split()[-1] not in a["titulo"].lower() and a["_modelo"] not in texto:
        return False
    a["km"] = extraer_km(texto)
    return a["km"] is None or a["km"] <= MAX_KM


def telegram(msg):
    tok, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if not (tok and chat):
        print("Telegram sin configurar:", msg[:80])
        return
    requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                  data={"chat_id": chat, "text": msg, "disable_web_page_preview": "false"}, timeout=20)


def formato(a):
    km = f"{a['km']:,} km".replace(",", ".") if a.get("km") else "km sin indicar"
    d = f" · a {a['dist_km']} km de Oviedo" if a.get("dist_km") is not None else ""
    return f"🚙 {a['titulo']}\n{int(a['precio'])} € · {km}\n{a['ciudad']}{d}\n{a['url']}"


def main():
    ahora = datetime.now(timezone.utc)
    try:
        prev = json.load(open(DATA, encoding="utf-8"))
    except Exception:
        prev = {"listings": []}
    conocidos = {a["id"]: a for a in prev["listings"]}
    primera = not conocidos
    nuevos = []

    for nombre, fn in FUENTES.items():
        for modelo in MODELOS:
            try:
                for a in fn(modelo):
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
            except Exception as e:
                print(f"[{nombre}] fallo con '{modelo}': {e}")
            time.sleep(1.5)

    limite = (ahora - timedelta(days=10)).isoformat()
    lista = [a for a in conocidos.values() if a["ultima_vez"] >= limite]
    lista.sort(key=lambda a: (a.get("dist_km") is None, a.get("dist_km") or 0))
    json.dump({"actualizado": ahora.isoformat(), "listings": lista},
              open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(lista)} anuncios, {len(nuevos)} nuevos")

    nuevos.sort(key=lambda a: (a.get("dist_km") is None, a.get("dist_km") or 0))
    if primera and nuevos:
        telegram(f"✅ Primer rastreo hecho: {len(nuevos)} anuncios guardados. "
                 "Te muestro los 5 más cercanos; a partir de ahora solo te aviso de los nuevos.")
        nuevos = nuevos[:5]
    for a in nuevos[:12]:
        telegram(formato(a))
    if len(nuevos) > 12:
        telegram(f"…y {len(nuevos) - 12} anuncios nuevos más en la app.")


if __name__ == "__main__":
    main()
