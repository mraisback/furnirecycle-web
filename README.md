# furnirecycle-web

A Python/Flask web app to merge multiple PDF files into one file (similar to online merge-PDF tools).

## Features
- Upload up to 20 PDF files
- Drag-and-drop reorder before merge
- Download merged PDF as `merged.pdf`

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000`.

## Run tests
```bash
pytest
```
