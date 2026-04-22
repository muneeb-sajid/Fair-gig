// src/routes/grievanceRoutes.js
const express = require('express');
const router = express.Router();
const grievanceController = require('../controllers/grievanceController');
const { verifyToken } = require('../middleware/auth');  // ← ADD THIS

// Public routes (no authentication)
router.get('/health', grievanceController.healthCheck);
router.get('/grievances', grievanceController.getAllGrievances);
router.get('/grievances/:id', grievanceController.getGrievanceById);
router.get('/analytics/complaints', grievanceController.getAnalytics);
router.post('/grievances/cluster', grievanceController.clusterComplaints);

// Protected routes (require authentication)
router.post('/grievances', verifyToken, grievanceController.createGrievance);
router.put('/grievances/:id', verifyToken, grievanceController.updateGrievance);
router.delete('/grievances/:id', verifyToken, grievanceController.deleteGrievance);
router.put('/grievances/:id/escalate', verifyToken, grievanceController.escalateGrievance);
router.post('/grievances/bulk-escalate', verifyToken, grievanceController.bulkEscalate);

module.exports = router;