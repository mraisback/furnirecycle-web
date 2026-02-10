from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass
from typing import List

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from pypdf import PdfReader, PdfWriter
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILES = 20

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


@dataclass
class UploadedPdf:
    name: str
    content: bytes


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def merge_pdfs(files: List[UploadedPdf]) -> io.BytesIO:
    writer = PdfWriter()

    for file in files:
        # pypdf works best when reading from file-like objects.
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(file.content)
            tmp.flush()
            reader = PdfReader(tmp.name)
            for page in reader.pages:
                writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output


@app.get("/")
def index():
    return render_template("index.html", max_files=MAX_FILES)


@app.post("/merge")
def merge():
    files = request.files.getlist("pdfs")

    if not files or all(not f.filename for f in files):
        flash("Please upload at least one PDF file.")
        return redirect(url_for("index"))

    if len(files) > MAX_FILES:
        flash(f"Please upload at most {MAX_FILES} files.")
        return redirect(url_for("index"))

    uploaded: List[UploadedPdf] = []
    for file in files:
        filename = secure_filename(file.filename)
        if not filename or not allowed_file(filename):
            flash("Only .pdf files are allowed.")
            return redirect(url_for("index"))
        content = file.read()
        if not content:
            flash(f"{filename} appears empty.")
            return redirect(url_for("index"))
        uploaded.append(UploadedPdf(name=filename, content=content))

    ordered_names = request.form.get("order", "").split(",")
    if ordered_names and any(ordered_names):
        name_to_file = {f.name: f for f in uploaded}
        reordered: List[UploadedPdf] = []
        for name in ordered_names:
            if name in name_to_file:
                reordered.append(name_to_file.pop(name))
        reordered.extend(name_to_file.values())
        uploaded = reordered

    merged = merge_pdfs(uploaded)
    return send_file(
        merged,
        as_attachment=True,
        download_name="merged.pdf",
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
