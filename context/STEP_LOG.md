# Step Log

## Step 01 — Project Initialization & Git Setup
- Created monorepo folders: client/, server/, ml-service/, docs/, context/
- Initialized Git, connected to GitHub remote
- Created .gitignore, README.md, context/PROJECT_CONTEXT.md, context/CURRENT_STATE.md
- Commit: "Step 01: Initialize FraudRing project structure and context system"
- Result: Clean, version-controlled project skeleton

## Step 02 — Backend Foundation
- Initialized Node.js project in server/
- Installed express, cors, dotenv, morgan (+ nodemon as dev dependency)
- Created server/src/app.js (Express app with health check, 404 handler, error handler)
- Created server/src/server.js (entry point)
- Created server/.env.example
- Verified server runs and /health returns 200 OK
- Commit: "Step 02: Backend foundation - Express server with health check"
- Result: Working minimal API server


## Step 03 — MongoDB Connection
- Installed mongoose
- Created MongoDB Atlas free-tier cluster and database user
- Created server/src/config/db.js (connection logic with error handling)
- Added MONGODB_URI to server/.env and server/.env.example
- Updated server/src/server.js to connect to DB before starting the server
- Verified successful connection and /health still working
- Commit: "Step 03: Connect MongoDB via Mongoose"
- Result: Backend has a working, persistent database connection



## Step 04 — Frontend Foundation
- Scaffolded React app in client/ using Vite
- Installed and configured Tailwind CSS
- Replaced App.jsx with a live backend health-check page
- Added client/.env and .env.example (VITE_API_URL)
- Verified frontend at localhost:5173 successfully calls backend /health
- Commit: "Step 04: Frontend foundation - React + Tailwind + backend health check"
- Result: Working full-stack skeleton, frontend and backend verified connected



## Step 05 — Synthetic Dataset Design
- Designed full entity schema: customers, devices, ip_addresses, addresses, payment_instruments, coupons, merchant_accounts, transactions, payment_attempts, refunds, chargebacks
- Defined graph relationships between entities
- Designed hidden ground-truth fields (ring_id, is_ring_transaction) for evaluation only
- Documented 8 abuse patterns to inject: account farming, device sharing, IP clustering, coupon abuse, refund abuse, coordinated timing, high-velocity, low-and-slow
- Defined time-based train/val/test split strategy (70/15/15) with held-out rings
- Created context/DATASET_SPEC.md
- Commit: "Step 05: Design synthetic dataset schema and ground-truth abuse-ring spec"
- Result: Clear blueprint ready for the dataset generator



## Step 06 — Synthetic Dataset Generator
- Set up Python venv in ml-service/, installed pandas, numpy, Faker
- Created data_generation/config.py (all tunable dataset parameters)
- Created data_generation/entity_generators.py (addresses, devices, IPs, instruments, coupons, merchants, customers)
- Created data_generation/ring_designer.py (assigns customers to hidden abuse rings + shared device/IP infrastructure)
- Created data_generation/generate_dataset.py (orchestrates generation, writes 11 CSVs to data/raw/)
- Verified generator runs cleanly and produces expected row counts and ring signal
- Commit: "Step 06: Build synthetic dataset generator with hidden abuse-ring ground truth"
- Result: Working, reproducible synthetic dataset with embedded ground truth for evaluation


## Step 07 — Data Validation
- Created data_validation/validate_dataset.py
- Checks: required files present, all foreign keys resolve, ring/non-ring class balance is realistic, rings show genuine shared-device/IP signal (not just 1:1 noise)
- All failures/warnings printed explicitly, never hidden
- Commit: "Step 07: Add dataset validation - referential integrity, class balance, ring signal strength"
- Result: Confirmed the dataset is trustworthy before any ML model is built on it