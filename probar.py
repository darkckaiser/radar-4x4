"""Diagnóstico: comprueba qué portales responden a un robot desde GitHub y cómo entregan los datos."""
import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "es-ES,es;q=0.9"}

PORTALES = {
    "Milanuncios": "https://www.milanuncios.com/coches-de-segunda-mano/?s=land%20cruiser&hasta=5000",
    "Coches.net": "https://www.coches.net/segunda-mano/?MaxPrice=5000",
    "Vibbo": "https://www.vibbo.com/coches-de-segunda-mano/?q=land%20cruiser",
    "Autocasion": "https://www.autocasion.com/coches-segunda-mano/todoterreno",
    "Coches.com": "https://www.coches.com/coches-segunda-mano/coches-ocasion-en-asturias.htm",
    "AutoScout24": "https://www.autoscout24.es/lst?priceto=5000&sort=age&desc=1",
}
MARCAS = {"cloudflare": "cloudflare", "datadome": "datadome", "captcha": "captcha",
          "acceso denegado": "access denied", "robot": "are you a robot"}

for nombre, url in PORTALES.items():
    try:
        r = requests.get(url, headers=H, timeout=25)
        t = r.text
        low = t.lower()
        bloqueos = [k for k, v in MARCAS.items() if v in low or k in low[:3000]]
        titulo = re.search(r"<title[^>]*>(.*?)</title>", t, re.S | re.I)
        print(f"== {nombre}: HTTP {r.status_code} · {len(t)} bytes · server={r.headers.get('server')}")
        print(f"   título: {(titulo.group(1).strip()[:80] if titulo else '-')}")
        print(f"   json-ld: {low.count('application/ld+json')} · __NEXT_DATA__: {low.count('__next_data__')} "
              f"· precios(€): {t.count('€')} · señales de bloqueo: {bloqueos or 'ninguna'}")
    except Exception as e:
        print(f"== {nombre}: ERROR {e}")
