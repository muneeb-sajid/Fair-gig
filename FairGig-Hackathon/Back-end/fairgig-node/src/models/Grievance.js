// src/models/Grievance.js
const mongoose = require('mongoose');

const grievanceSchema = new mongoose.Schema({
  workerId: { type: String, required: true, index: true },  // ← ADD THIS LINE
  platform: { type: String, required: true },
  category: { type: String, required: true },
  description: { type: String, required: true },
  tags: [{ type: String }],
  status: { 
    type: String, 
    enum: ['pending', 'in-review', 'escalated', 'resolved', 'rejected'],
    default: 'pending' 
  },
  priority: {
    type: String,
    enum: ['low', 'medium', 'high', 'urgent'],
    default: 'low'
  },
  escalatedBy: { type: String },
  escalatedAt: { type: Date },
  resolvedAt: { type: Date },
  resolutionNote: { type: String },
  clusterId: { type: String },
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now }
});

module.exports = mongoose.model('Grievance', grievanceSchema);