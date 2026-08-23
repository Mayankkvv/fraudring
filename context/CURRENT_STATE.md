# Current State

## Status
Step 5 complete — dataset schema and ground-truth design finalized.

## Completed steps
- Step 01: Project initialization & Git setup
- Step 02: Backend foundation (Express server + health check)
- Step 03: MongoDB connection (Mongoose + Atlas, with dns.setServers fix)
- Step 04: Frontend foundation (React + Vite + Tailwind v3, live backend health check)
- Step 05: Synthetic dataset design (schema + ground-truth abuse-ring spec in context/DATASET_SPEC.md)

## Current folder structure
fraudring/
├── client/  (React + Vite + Tailwind v3)
├── server/  (Express + Mongoose)
├── ml-service/
├── docs/
├── context/  (includes DATASET_SPEC.md)
├── .gitignore
└── README.md

## Current tech stack
Frontend: React, Vite, Tailwind CSS v3
Backend: Node.js, Express, cors, dotenv, morgan, nodemon, mongoose, MongoDB Atlas

## Current branch
main

## What works
- Backend + MongoDB connection verified
- Frontend + backend health check verified
- Full dataset schema and abuse-ring ground-truth design documented

## What does not work
No dataset actually generated yet, no ML service, no graph engine, no real API routes beyond /health.

## Current task
Review DATASET_SPEC.md and push Step 5.

## Next planned step
Step 06 — Build the synthetic dataset generator (Python script producing the entities in DATASET_SPEC.md).

## Known issues
- server/src/config/db.js requires dns.setServers(['8.8.8.8','1.1.1.1']) — keep in future edits
- client tailwindcss must stay pinned to v3 (not v4) — keep in future edits

## Environment variables required
- server/.env: PORT, MONGODB_URI
- client/.env: VITE_API_URL