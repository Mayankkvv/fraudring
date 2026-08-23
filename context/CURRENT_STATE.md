# Current State

## Status
Step 4 complete — frontend and backend are connected and verified end-to-end.

## Completed steps
- Step 01: Project initialization & Git setup
- Step 02: Backend foundation (Express server + health check)
- Step 03: MongoDB connection (Mongoose + Atlas, with dns.setServers fix for SRV lookup issues)
- Step 04: Frontend foundation (React + Vite + Tailwind, live backend health check)

## Current folder structure
fraudring/
├── client/  (React + Vite + Tailwind)
├── server/  (Express + Mongoose)
├── ml-service/
├── docs/
├── context/
├── .gitignore
└── README.md

## Current tech stack
Frontend: React, Vite, Tailwind CSS
Backend: Node.js, Express, cors, dotenv, morgan, nodemon, mongoose, MongoDB Atlas

## Current branch
main

## What works
- Backend runs on http://localhost:5000, connected to MongoDB Atlas
- Frontend runs on http://localhost:5173, successfully calls backend /health and displays live status

## What does not work
No Mongoose models/schemas, no real API routes beyond /health, no ML service, no dataset yet.

## Current task
Verify frontend shows "Backend status: ok" with both servers running, then push Step 4.

## Next planned step
Step 05 — Synthetic fintech dataset design (schema for customers, transactions, devices, IPs, etc.)

## Known issues
- server/src/config/db.js requires dns.setServers(['8.8.8.8','1.1.1.1']) to work around SRV DNS blocking on some Indian ISPs — keep this line in all future edits to that file

## Environment variables required
- server/.env: PORT, MONGODB_URI
- client/.env: VITE_API_URL