# Memory Block — Warehouse 3D Inventory

A live 3D warehouse inventory viewer built with Flask + SQLite + Three.js.

---

## Run locally (2 minutes)

### 1. Install Python dependencies

```bash
cd warehouse-app
pip install -r requirements.txt
```

### 2. Start the server

```bash
python app.py
```

### 3. Open in browser

```
http://localhost:5000
```

The database (`warehouse.db`) is created and seeded automatically on first run.
All edits you make in the 3D viewer are saved to SQLite and persist across restarts.

---

## Project structure

```
warehouse-app/
├── app.py              ← Flask server + API routes
├── database.py         ← SQLite helpers (init, seed, queries)
├── warehouse.db        ← Auto-created on first run
├── requirements.txt    ← Python dependencies
├── Procfile            ← For Railway/Render deployment
└── templates/
    └── index.html      ← Three.js 3D viewer (served by Flask)
```

---

## API endpoints

| Method | URL | What it does |
|--------|-----|--------------|
| GET | `/` | Serves the 3D viewer |
| GET | `/api/pallets` | Returns all pallets as JSON |
| PATCH | `/api/pallets/<id>` | Updates a pallet (fill, units, name, sku) |
| GET | `/api/stats` | Returns total / full / low / empty counts |

---

## Deploy to Railway (free, ~10 minutes)

1. Create a free account at **railway.app**
2. Install Railway CLI: `npm install -g @railway/cli`
3. From the `warehouse-app` folder:

```bash
railway login
railway init
railway up
```

4. Railway gives you a public URL — share it with your team.

> Note: SQLite works fine for a small team. If you need multiple people
> editing simultaneously at scale, swap to PostgreSQL (Railway has a
> free Postgres plugin — update `database.py` to use `psycopg2`).

---

## Controls (in the 3D viewer)

| Action | How |
|--------|-----|
| Look around | Right-click + drag |
| Move forward/back | Scroll wheel |
| Walk | WASD or arrow keys |
| Select pallet | Left-click |
| Orbit view | Click 🔄 Orbit view button |
| Teleport | Click minimap |

---

## Resetting the database

Delete `warehouse.db` and restart — it will reseed fresh.

```bash
rm warehouse.db
python app.py
```
