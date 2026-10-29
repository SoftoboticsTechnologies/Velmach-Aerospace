"""Export the 3D logo concepts in assets/logo-3d/velmach-3d-logo.html to PNG and GLB files.

Opens the page in headless Edge with #export, reads the JSON it writes into <pre id="export">,
and saves each file under assets/logo-3d/export/. Usage: python tools/export-3d-logo.py
"""
import base64, html, json, pathlib, re, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "assets/logo-3d/velmach-3d-logo.html"
OUT = ROOT / "assets/logo-3d/export"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

dom = subprocess.run(
    [EDGE, "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
     "--window-size=1300,1700", "--virtual-time-budget=30000", "--dump-dom", PAGE.as_uri() + "#export"],
    capture_output=True, text=True, encoding="utf-8", timeout=180).stdout
# The last match is the element; earlier ones are the page's own comment text.
found = re.findall(r'<pre id="export"[^>]*>(\{.*?)</pre>', dom, re.S)
if not found:
    raise SystemExit("Export data not found: the page did not finish rendering in time.")
for name, data in json.loads(html.unescape(found[-1])).items():
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(data))
    print(f"{path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")
