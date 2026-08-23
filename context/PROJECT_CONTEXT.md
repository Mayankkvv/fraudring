# FraudRing — Project Context

## What this is
An AI-powered platform that detects **coordinated fraud/abuse rings** in a synthetic Razorpay-like payment ecosystem, not just single suspicious transactions.

## Core pipeline
Transaction risk model → behavioral anomaly detection → entity relationship graph → abuse-ring detection → financial exposure calculation → recommended action → AI investigation/explanation → audit trail

## Key principle
Detection comes from ML + anomaly detection + graph analysis + rules — **never** the LLM. The LLM is only used for investigation, explanation, summarization, and natural-language querying, and must never invent evidence.

## Target architecture
React Frontend → Node.js/Express API → Redis + BullMQ → Python ML/Risk Service (XGBoost, anomaly model, graph engine, risk engine) → MongoDB → Investigation/Audit System → LLM Investigation Agent

## Working process
- One implementation step at a time — never skip ahead
- Every step ends with a Git commit + push
- `context/CURRENT_STATE.md` is always kept up to date so a new chat can resume this project