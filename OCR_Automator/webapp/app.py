import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, session, send_file, flash
import json

# Ensure we can import the OCR pipeline from OCR_Automator package root
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from process_itau_unified_v1 import process_pdf_files as process_itau_files
from process_santander_unified_v1 import process_pdf_files as process_santander_files

app = Flask(__name__)
# Secret key for sessions - override with env var in production
app.secret_key = os.environ.get("OCR_AUTOMATOR_SECRET", "dev-secret-change-me")

CONFIG_PATH = BASE_DIR / "config" / "web_config.json"

def load_credentials():
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            users = {u.get("username"): u.get("password") for u in data.get("users", [])}
            return users
        except Exception:
            pass
    # default creds (dev only)
    return {"admin": "change_me"}

USERS = load_credentials()


def login_required(view_func):
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if USERS.get(username) == password:
            session["user"] = username
            return redirect(url_for("upload"))
        flash("Credenciales inválidas", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET"])  # redirect to upload
def root():
    if session.get("user"):
        return redirect(url_for("upload"))
    return redirect(url_for("login"))


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        files = request.files.getlist("pdfs")
        bank = (request.form.get("bank") or "itau").lower()
        geocode_flag = bool(request.form.get("geocode"))
        quality = (request.form.get("quality") or "standard").lower()
        dpi_val = 300 if quality == "high" else (150 if quality == "fast" else 200)
        if not files:
            flash("Sube al menos un PDF", "error")
            return redirect(url_for("upload"))
        # Save to temp folder per request
        tmp_dir = BASE_DIR / "web_uploads" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        pdf_paths = []
        for f in files:
            fname = (f.filename or "").lower()
            if not fname.endswith(".pdf"):
                continue
            dest = tmp_dir / Path(f.filename or "documento.pdf").name
            f.save(dest)
            pdf_paths.append(str(dest))
        if not pdf_paths:
            flash("No se detectaron PDFs válidos", "error")
            return redirect(url_for("upload"))
        try:
            if bank == "santander":
                out_dir = BASE_DIR / "outputs" / "Santander" / "web"
                excel_path, debug_path = process_santander_files(pdf_paths, geocode=geocode_flag, output_dir=str(out_dir), dpi=dpi_val)
            else:
                out_dir = BASE_DIR / "outputs" / "Itau" / "web"
                excel_path, debug_path = process_itau_files(pdf_paths, geocode=geocode_flag, output_dir=str(out_dir), dpi=dpi_val)
            # Redirigir a resultados para ofrecer enlaces a Excel y Debug
            session["last_result_excel"] = excel_path
            session["last_result_debug"] = debug_path
            session["last_result_bank"] = "santander" if bank == "santander" else "itau"
            session["last_bank"] = session["last_result_bank"]
            flash("Procesamiento completado. Descarga disponible abajo.", "info")
            return redirect(url_for("results"))
        except Exception as e:
            flash(f"Error procesando PDFs: {e}", "error")
            return redirect(url_for("upload"))
        finally:
            # Limpiar subidas temporales
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
    return render_template("upload.html", user=session.get("user"), selected_bank=session.get("last_bank", "itau"))


@app.route("/results", methods=["GET"]) 
@login_required
def results():
    base_itau = BASE_DIR / "outputs" / "Itau" / "web"
    base_sant = BASE_DIR / "outputs" / "Santander" / "web"
    base_itau.mkdir(parents=True, exist_ok=True)
    base_sant.mkdir(parents=True, exist_ok=True)

    # Buscar archivos recientes Itau
    excels_itau = sorted(base_itau.glob("Itau_results_UNIFIED_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    items_itau = []
    for x in excels_itau[:20]:
        ts = x.stem.replace("Itau_results_UNIFIED_", "")
        debug = base_itau / f"Itau_debug_unified_{ts}.txt"
        items_itau.append({
            "ts": ts,
            "excel": x.name,
            "debug": debug.name if debug.exists() else None,
            "mtime": datetime.fromtimestamp(x.stat().st_mtime).strftime("%d-%m-%Y %H:%M")
        })

    # Buscar archivos recientes Santander
    excels_sant = sorted(base_sant.glob("Santander_results_UNIFIED_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    items_sant = []
    for x in excels_sant[:20]:
        ts = x.stem.replace("Santander_results_UNIFIED_", "")
        debug = base_sant / f"Santander_debug_unified_{ts}.txt"
        items_sant.append({
            "ts": ts,
            "excel": x.name,
            "debug": debug.name if debug.exists() else None,
            "mtime": datetime.fromtimestamp(x.stat().st_mtime).strftime("%d-%m-%Y %H:%M")
        })

    last_excel = session.pop("last_result_excel", None)
    last_debug = session.pop("last_result_debug", None)
    last_bank = session.pop("last_result_bank", None)
    last_excel_name = Path(last_excel).name if last_excel else None
    last_debug_name = Path(last_debug).name if last_debug else None
    return render_template(
        "results.html",
        items_itau=items_itau,
        items_santander=items_sant,
        last_excel=last_excel_name,
        last_debug=last_debug_name,
        last_bank=last_bank,
    )


@app.route("/download/<bank>/<path:filename>")
@login_required
def download(bank: str, filename: str):
    bank_l = (bank or "itau").lower()
    if bank_l == "santander":
        base = BASE_DIR / "outputs" / "Santander" / "web"
    else:
        base = BASE_DIR / "outputs" / "Itau" / "web"
    file_path = (base / filename).resolve()
    try:
        base_resolved = base.resolve()
    except Exception:
        base_resolved = base
    # Evitar traversal
    if not str(file_path).startswith(str(base_resolved)) or not file_path.exists():
        flash("Archivo no disponible", "error")
        return redirect(url_for("results"))
    return send_file(str(file_path), as_attachment=True, download_name=file_path.name)


# --- Legal pages ---
@app.route("/legal/terminos")
def terms():
    return render_template("terms.html")


@app.route("/legal/privacidad")
def privacy():
    return render_template("privacy.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
