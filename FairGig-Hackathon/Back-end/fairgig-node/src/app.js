// src/app.js
const express = require('express');
const cors = require('cors');
const grievanceRoutes = require('./routes/grievanceRoutes');
const errorHandler = require('./middleware/errorHandler');

const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.use('/api', grievanceRoutes);

// Error handler
app.use(errorHandler);

module.exports = app;