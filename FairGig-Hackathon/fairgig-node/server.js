// server.js
require('dotenv').config();
const app = require('./src/app');
const connectDB = require('./src/config/database');

const PORT = process.env.PORT || 3001;

// Connect to database
connectDB();

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Grievance Service running on http://localhost:${PORT}`);
  console.log(`📋 Endpoints:`);
  console.log(`   POST   /api/grievances           - Create complaint`);
  console.log(`   GET    /api/grievances           - List complaints (with filters)`);
  console.log(`   GET    /api/grievances/:id       - Get complaint by ID`);
  console.log(`   PUT    /api/grievances/:id       - Update complaint`);
  console.log(`   DELETE /api/grievances/:id       - Delete complaint`);
  console.log(`   POST   /api/grievances/cluster   - Cluster complaints`);
  console.log(`   PUT    /api/grievances/:id/escalate - Escalate complaint`);
  console.log(`   POST   /api/grievances/bulk-escalate - Bulk escalate`);
  console.log(`   GET    /api/analytics/complaints - Analytics`);
  console.log(`   GET    /api/health               - Health check`);
});