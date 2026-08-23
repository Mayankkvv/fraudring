# FraudRing

AI-powered coordinated fraud and merchant-abuse detection platform, built for Razorpay's AI Risk Manager Buildathon (Track 02: stop merchants losing money to fraud, returns, and chargebacks).

FraudRing looks past individual transactions to detect **coordinated abuse rings** — groups of accounts that look harmless alone but share devices, IPs, addresses, and behavior patterns.

## Status
🚧 Under active development. See `context/CURRENT_STATE.md` for the latest project status.

## Stack
- **Frontend:** React, Tailwind, React Flow/Cytoscape.js, Recharts
- **Backend:** Node.js, Express, MongoDB, Redis, BullMQ, Socket.IO
- **ML:** Python, FastAPI, Pandas, NumPy, Scikit-learn, XGBoost, NetworkX, SHAP
- **AI:** LLM-based investigation agent (Groq/OpenAI-compatible API)