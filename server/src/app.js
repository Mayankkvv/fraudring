const express = require('express');
const cors = require('cors');
const morgan = require('morgan');

const app = express();

// Middleware
app.use(cors());
app.use(express.json());
app.use(morgan('dev'));

// Health check route - confirms the API is alive and reachable
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'ok',
    service: 'fraudring-api',
    timestamp: new Date().toISOString(),
  });
});

// 404 handler - runs when no route matches the request
app.use((req, res) => {
  res.status(404).json({ error: 'Route not found' });
});

// Global error handler - catches errors thrown anywhere in routes
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

module.exports = app;