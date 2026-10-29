"""Print assets/logo-3d/pdf-sheet.html to assets/logo-3d/velmach-3d-logo.pdf with headless Edge.

Run tools/export-3d-logo.py first: the sheet uses the PNGs in assets/logo-3d/export/.
Usage: python tools/build-3d-logo-pdf.py
"""
import pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHEET = ROOT / "assets/logo-3d/pdf-sheet.html"
PDF = ROOT / "assets/logo-3d/velmach-3d-logo.pdf"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

subprocess.run(
    [EDGE, "--headless=new", "--no-pdf-header-footer", "--virtual-time-budget=15000",
     f"--print-to-pdf={PDF}", SHEET.as_uri()],
    capture_output=True, timeout=180, check=True)
print(f"{PDF.relative_to(ROOT)}  {PDF.stat().st_size // 1024} KB")
