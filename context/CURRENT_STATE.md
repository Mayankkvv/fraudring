# Current State

## Status
Step 6 complete — synthetic dataset generator built and producing data.

## Completed steps
- Step 01: Project initialization & Git setup
- Step 02: Backend foundation (Express server + health check)
- Step 03: MongoDB connection (Mongoose + Atlas, with dns.setServers fix)
- Step 04: Frontend foundation (React + Vite + Tailwind v3, live backend health check)
- Step 05: Synthetic dataset design (schema + ground-truth abuse-ring spec)
- Step 06: Synthetic dataset generator (Python, produces CSVs in ml-service/data/raw/)

## Current folder structure
fraudring/
├── client/  (React + Vite + Tailwind v3)
├── server/  (Express + Mongoose)
├── ml-service/  (Python venv, data_generation/, data/raw/*.csv)
├── docs/
├── context/
├── .gitignore
└── README.md

## Current tech stack
Frontend: React, Vite, Tailwind CSS v3
Backend: Node.js, Express, Mongoose, MongoDB Atlas
ML: Python, pandas, numpy, Faker (dataset generation only so far - no models yet)

## Current branch
main

## What works
- Backend + MongoDB verified
- Frontend + backend health check verified
- Synthetic dataset generator runs end-to-end and produces 11 CSV files with hidden ring_id/is_ring_transaction ground truth

## What does not work
No data validation step yet, no ML risk model, no graph engine, no real API routes beyond /health.

## Current task
Run the generator, confirm CSVs look correct, and push Step 6.

## Next planned step
Step 07 — Data validation (sanity-check the generated CSVs: row counts, referential integrity, ring signal strength).

## Known issues
- server/src/config/db.js requires dns.setServers(['8.8.8.8','1.1.1.1']) — keep in future edits
- client tailwindcss must stay pinned to v3 (not v4) — keep in future edits

## Environment variables required
- server/.env: PORT, MONGODB_URI
- client/.env: VITE_API_URL