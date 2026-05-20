# kat-text-tool

A web platform for visualising textual variants across multiple manuscript witnesses.
Built around TEI XML inputs, with automatic segment alignment, variant-graph
collation, and an interactive comparison dashboard.

## Architecture

```
kat-text-tool/
├── backend/      FastAPI + lxml — TEI parsing, alignment, similarity
├── frontend/     Vue 3 + Vite + D3 — dashboard and collation view
└── docker-compose.yml
```

## Quick start

### With Docker (recommended)

```bash
docker compose up --build
```

Visit <http://localhost:3000>.

### Without Docker

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Acknowledgments

Built with [Katharina Zwinger](https://github.com/katzmo) at the VDA Research Group,
University of Vienna.
