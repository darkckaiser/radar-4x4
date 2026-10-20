"""Diagnóstico 2: muestra cómo guardan los anuncios Coches.net, Coches.com y AutoScout24."""
import json, re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "es-ES,es;q=0.9"}
URLS = {
    "Coches.net": "https://www.coches.net/segunda-mano/?MaxPrice=5000",
    "Coches.com": "https://www.coches.com/coches-segunda-mano/coches-ocasion-en-asturias.htm",
    "AutoScout24": "https://www.autoscout24.es/lst?priceto=5000&sort=age&desc=1",
}


def listas(o, ruta="", out=None, prof=0):
    out = [] if out is None else out
    if prof > 12:
        return out
    if isinstance(o, list):
        if len(o) >= 5 and all(isinstance(x, dict) for x in o[:5]):
            out.append((ruta, o))
        for i, x in enumerate(o[:3]):
            listas(x, f"{ruta}[{i}]", out, prof + 1)
    elif isinstance(o, dict):
        for k, v in o.items():
            listas(v, f"{ruta}.{k}", out, prof + 1)
    return out


for nombre, url in URLS.items():
    print(f"\n######## {nombre}")
    try:
        t = requests.get(url, headers=H, timeout=25).text
    except Exception as e:
        print("ERROR", e)
        continue
    for attrs, cuerpo in re.findall(r"<script([^>]*)>(.*?)</script>", t, re.S | re.I):
        grande = len(cuerpo) > 30000
        es_json = "ld+json" in attrs or "__NEXT_DATA__" in attrs
        if not (grande or es_json):
            continue
        print(f"-- script {attrs.strip()[:70]!r} · {len(cuerpo)} chars · empieza: {cuerpo.strip()[:90]!r}")
        try:
            datos = json.loads(cuerpo)
        except Exception:
            continue
        for ruta, lst in listas(datos)[:3]:
            print(f"   lista {ruta} ({len(lst)} elementos) claves: {list(lst[0].keys())[:25]}")
            print(f"   ejemplo: {json.dumps(lst[0], ensure_ascii=False)[:500]}")
