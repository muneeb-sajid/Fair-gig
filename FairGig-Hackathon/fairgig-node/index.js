// index.js
require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// MongoDB Connection
mongoose.connect(process.env.MONGODB_URI)
  .then(() => console.log('✅ MongoDB Connected for Grievance Service'))
  .catch(err => console.error('❌ MongoDB Error:', err));

// ==========================================
// SCHEMAS
// ==========================================

// Worker Schema (for Auth)
const workerSchema = new mongoose.Schema({
  name: { type: String, required: true },
  email: { type: String, required: true, unique: true },
  password: { type: String, required: true },
  phone: { type: String, required: true },
  city: { type: String, default: 'Lahore' },
  platform: { type: String, required: true }, // Uber, Foodpanda, Careem, etc.
  totalEarnings: { type: Number, default: 0 },
  createdAt: { type: Date, default: Date.now }
});

const Worker = mongoose.model('Worker', workerSchema);

// Grievance Schema
const grievanceSchema = new mongoose.Schema({
  workerId: { type: mongoose.Schema.Types.ObjectId, ref: 'Worker' },
  platform: { type: String, required: true },
  category: { type: String, required: true },
  description: { type: String, required: true },
  status: { type: String, default: 'Pending' },
  createdAt: { type: Date, default: Date.now }
});

const Grievance = mongoose.model('Grievance', grievanceSchema);

// Earnings Schema
const earningSchema = new mongoose.Schema({
  workerId: { type: mongoose.Schema.Types.ObjectId, ref: 'Worker', required: true },
  amount: { type: Number, required: true },
  platform: { type: String, required: true },
  date: { type: String, required: true }, // YYYY-MM-DD
  createdAt: { type: Date, default: Date.now }
});

const Earning = mongoose.model('Earning', earningSchema);

// ==========================================
// MIDDLEWARE: Verify JWT Token
// ==========================================
const verifyToken = (req, res, next) => {
  const authHeader = req.headers.authorization;
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ success: false, message: 'No token provided' });
  }
  
  const token = authHeader.split(' ')[1];
  
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.workerId = decoded.workerId;
    next();
  } catch (error) {
    return res.status(401).json({ success: false, message: 'Invalid token' });
  }
};

// ==========================================
// AUTH API ENDPOINTS
// ==========================================

// POST /api/auth/register - Register a new worker
app.post('/api/auth/register', async (req, res) => {
  try {
    const { name, email, password, phone, city, platform } = req.body;
    
    // Check if worker already exists
    const existingWorker = await Worker.findOne({ email });
    if (existingWorker) {
      return res.status(400).json({ success: false, message: 'Email already registered' });
    }
    
    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);
    
    // Create new worker
    const worker = new Worker({
      name,
      email,
      password: hashedPassword,
      phone,
      city: city || 'Lahore',
      platform
    });
    
    await worker.save();
    
    // Create JWT token
    const token = jwt.sign(
      { workerId: worker._id, email: worker.email },
      process.env.JWT_SECRET,
      { expiresIn: process.env.JWT_EXPIRE }
    );
    
    res.status(201).json({
      success: true,
      message: 'Worker registered successfully',
      token,
      worker: {
        id: worker._id,
        name: worker.name,
        email: worker.email,
        platform: worker.platform,
        city: worker.city
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// POST /api/auth/login - Login worker
app.post('/api/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    
    // Find worker by email
    const worker = await Worker.findOne({ email });
    if (!worker) {
      return res.status(401).json({ success: false, message: 'Invalid credentials' });
    }
    
    // Check password
    const isPasswordValid = await bcrypt.compare(password, worker.password);
    if (!isPasswordValid) {
      return res.status(401).json({ success: false, message: 'Invalid credentials' });
    }
    
    // Create JWT token
    const token = jwt.sign(
      { workerId: worker._id, email: worker.email },
      process.env.JWT_SECRET,
      { expiresIn: process.env.JWT_EXPIRE }
    );
    
    res.json({
      success: true,
      message: 'Login successful',
      token,
      worker: {
        id: worker._id,
        name: worker.name,
        email: worker.email,
        platform: worker.platform,
        city: worker.city,
        totalEarnings: worker.totalEarnings
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// GET /api/auth/profile - Get worker profile (Protected)
app.get('/api/auth/profile', verifyToken, async (req, res) => {
  try {
    const worker = await Worker.findById(req.workerId).select('-password');
    if (!worker) {
      return res.status(404).json({ success: false, message: 'Worker not found' });
    }
    
    res.json({ success: true, worker });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// GET /api/workers - Get all workers (For Advocate Dashboard)
app.get('/api/workers', async (req, res) => {
  try {
    const workers = await Worker.find().select('-password').sort({ createdAt: -1 });
    res.json({ success: true, count: workers.length, workers });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// ==========================================
// EARNINGS API ENDPOINTS
// ==========================================

// POST /api/earnings - Add earnings for a worker
app.post('/api/earnings', verifyToken, async (req, res) => {
  try {
    const { amount, platform, date } = req.body;
    
    const earning = new Earning({
      workerId: req.workerId,
      amount,
      platform,
      date
    });
    
    await earning.save();
    
    // Update worker's total earnings
    await Worker.findByIdAndUpdate(req.workerId, {
      $inc: { totalEarnings: amount }
    });
    
    res.status(201).json({ success: true, message: 'Earnings added', earning });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// GET /api/earnings - Get logged-in worker's earnings
app.get('/api/earnings', verifyToken, async (req, res) => {
  try {
    const earnings = await Earning.find({ workerId: req.workerId }).sort({ date: -1 });
    res.json({ success: true, count: earnings.length, earnings });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// GET /api/earnings/:workerId - Get earnings by worker ID (For advocate)
app.get('/api/earnings/:workerId', async (req, res) => {
  try {
    const earnings = await Earning.find({ workerId: req.params.workerId }).sort({ date: -1 });
    res.json({ success: true, count: earnings.length, earnings });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// ==========================================
// GRIEVANCE API ENDPOINTS (Updated with workerId)
// ==========================================

// POST /api/grievances - Create a complaint (Protected)
app.post('/api/grievances', verifyToken, async (req, res) => {
  try {
    const { platform, category, description } = req.body;
    
    const newGrievance = new Grievance({
      workerId: req.workerId,
      platform,
      category,
      description
    });
    
    await newGrievance.save();
    res.status(201).json({ success: true, message: 'Complaint logged successfully', data: newGrievance });
  } catch (error) {
    res.status(400).json({ success: false, error: error.message });
  }
});

// GET /api/grievances - List complaints (with optional platform filter)
app.get('/api/grievances', async (req, res) => {
  try {
    const filter = req.query.platform ? { platform: req.query.platform } : {};
    const grievances = await Grievance.find(filter)
      .populate('workerId', 'name email platform')
      .sort({ createdAt: -1 });
    res.json({ success: true, count: grievances.length, data: grievances });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// GET /api/analytics/complaints - Aggregate analytics
app.get('/api/analytics/complaints', async (req, res) => {
  try {
    const aggregateData = await Grievance.aggregate([
      { $group: { _id: '$category', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);
    
    const formattedData = {};
    aggregateData.forEach(item => {
      formattedData[item._id] = item.count;
    });
    
    res.json({ success: true, analytics: formattedData });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// GET /api/health - Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'OK', service: 'Grievance Service', port: process.env.PORT });
});

// ==========================================
// START SERVER
// ==========================================
const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`🚀 Grievance Service running on http://localhost:${PORT}`);
  console.log(`📋 Endpoints:`);
  console.log(`   AUTH:`);
  console.log(`   POST   http://localhost:${PORT}/api/auth/register`);
  console.log(`   POST   http://localhost:${PORT}/api/auth/login`);
  console.log(`   GET    http://localhost:${PORT}/api/auth/profile (Protected)`);
  console.log(`   EARNINGS:`);
  console.log(`   POST   http://localhost:${PORT}/api/earnings (Protected)`);
  console.log(`   GET    http://localhost:${PORT}/api/earnings (Protected)`);
  console.log(`   GRIEVANCES:`);
  console.log(`   POST   http://localhost:${PORT}/api/grievances (Protected)`);
  console.log(`   GET    http://localhost:${PORT}/api/grievances`);
  console.log(`   GET    http://localhost:${PORT}/api/analytics/complaints`);
});

// GET /api/earnings/city-median - Calculate Lahore city median
app.get('/api/earnings/city-median', async (req, res) => {
  try {
    // Get all workers in Lahore
    const workers = await Worker.find({ city: 'Lahore', role: 'worker' });
    const workerIds = workers.map(w => w._id);
    
    // Get all earnings for these workers
    const earnings = await Earning.find({ workerId: { $in: workerIds } });
    
    if (earnings.length === 0) {
      return res.json({ success: true, median: 0, message: 'No earnings data yet' });
    }
    
    // Calculate median
    const amounts = earnings.map(e => e.amount).sort((a, b) => a - b);
    const mid = Math.floor(amounts.length / 2);
    const median = amounts.length % 2 === 0 
      ? (amounts[mid - 1] + amounts[mid]) / 2 
      : amounts[mid];
    
    res.json({
      success: true,
      city: 'Lahore',
      median: median,
      totalEarningsCount: earnings.length,
      totalWorkers: workers.length
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// POST /api/detect-anomaly - Detect 20% income drop
app.post('/api/detect-anomaly', async (req, res) => {
  try {
    const { shifts } = req.body; // Array of last 5 shifts with net earnings
    
    if (!shifts || shifts.length < 3) {
      return res.json({ 
        flagged: false, 
        explanation: "Insufficient shift data for anomaly detection" 
      });
    }
    
    // Calculate average of previous shifts (excluding latest)
    const previousShifts = shifts.slice(0, -1);
    const latestShift = shifts[shifts.length - 1];
    
    const avgPrevious = previousShifts.reduce((sum, s) => sum + s.net, 0) / previousShifts.length;
    const dropPercentage = ((avgPrevious - latestShift.net) / avgPrevious) * 100;
    
    if (dropPercentage >= 20) {
      return res.json({
        flagged: true,
        explanation: `Statistically unusual income drop of ${dropPercentage.toFixed(1)}%. Platform deductions increased significantly.`,
        dropPercentage: dropPercentage.toFixed(1),
        previousAverage: avgPrevious,
        latestEarning: latestShift.net
      });
    }
    
    res.json({
      flagged: false,
      explanation: `Income stable. Drop of ${dropPercentage.toFixed(1)}% within normal range.`
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});