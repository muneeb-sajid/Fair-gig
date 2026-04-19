// src/routes/grievanceRoutes.js
const express = require('express');
const router = express.Router();
const grievanceController = require('../controllers/grievanceController');

// Health check
router.get('/health', grievanceController.healthCheck);

// Grievance routes (ALL endpoints from original code)
router.post('/grievances', grievanceController.createGrievance);
router.get('/grievances', grievanceController.getAllGrievances);
router.get('/grievances/:id', grievanceController.getGrievanceById);
router.put('/grievances/:id', grievanceController.updateGrievance);
router.delete('/grievances/:id', grievanceController.deleteGrievance);
router.put('/grievances/:id/escalate', grievanceController.escalateGrievance);
router.post('/grievances/cluster', grievanceController.clusterComplaints);
router.post('/grievances/bulk-escalate', grievanceController.bulkEscalate);
router.get('/analytics/complaints', grievanceController.getAnalytics);

module.exports = router;