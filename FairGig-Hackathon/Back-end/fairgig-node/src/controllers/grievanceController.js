const { autoTag, calculatePriority } = require('../utils/helpers');
const Grievance = require('../models/Grievance');  // ← MUST BE THERE
// In src/controllers/grievanceController.js
exports.createGrievance = async (req, res) => {
  try {
    const { platform, category, description } = req.body;
    
    // Log to see what's coming in (for debugging)
    console.log('Received:', { platform, category, description });
    
    // Check if req.workerId exists (from JWT)
    if (!req.workerId) {
      return res.status(401).json({ success: false, error: 'Unauthorized - No worker ID' });
    }
    
    // Validate required fields
    if (!platform || !category || !description) {
      return res.status(400).json({ 
        success: false, 
        error: 'Missing required fields: platform, category, description' 
      });
    }
    
    const tags = autoTag(description, category);
    const priority = calculatePriority(description, category);
    
    const newGrievance = new Grievance({
      workerId: req.workerId,
      platform,
      category,
      description,
      tags,
      priority,
      status: 'pending'
    });
    
    await newGrievance.save();
    
    res.status(201).json({ 
      success: true, 
      message: 'Complaint logged successfully', 
      data: newGrievance 
    });
  } catch (error) {
    console.error('Error creating grievance:', error);
    res.status(400).json({ success: false, error: error.message });
  }
};

// READ ALL - GET /api/grievances (with filters)
exports.getAllGrievances = async (req, res) => {
  try {
    const filter = {};
    if (req.query.platform) filter.platform = req.query.platform;
    if (req.query.category) filter.category = req.query.category;
    if (req.query.status) filter.status = req.query.status;
    if (req.query.priority) filter.priority = req.query.priority;
    
    const grievances = await Grievance.find(filter).sort({ createdAt: -1 });
    
    res.json({ 
      success: true, 
      count: grievances.length, 
      data: grievances 
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

// READ ONE - GET /api/grievances/:id
exports.getGrievanceById = async (req, res) => {
  try {
    const grievance = await Grievance.findById(req.params.id);
    if (!grievance) {
      return res.status(404).json({ success: false, message: 'Complaint not found' });
    }
    res.json({ success: true, data: grievance });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

// UPDATE - PUT /api/grievances/:id
exports.updateGrievance = async (req, res) => {
  try {
    const { platform, category, description, status, priority, resolutionNote } = req.body;
    
    const grievance = await Grievance.findById(req.params.id);
    if (!grievance) {
      return res.status(404).json({ success: false, message: 'Complaint not found' });
    }
    
    // ← ADD PERMISSION CHECK
    if (grievance.workerId !== req.workerId) {
      return res.status(403).json({ success: false, message: 'You can only update your own complaints' });
    }
    
    if (platform) grievance.platform = platform;
    if (category) grievance.category = category;
    if (description) grievance.description = description;
    if (status) grievance.status = status;
    if (priority) grievance.priority = priority;
    if (resolutionNote) grievance.resolutionNote = resolutionNote;
    
    if (description) {
      grievance.tags = autoTag(description, grievance.category);
    }
    
    if (status === 'resolved' && grievance.status !== 'resolved') {
      grievance.resolvedAt = new Date();
    }
    
    grievance.updatedAt = new Date();
    await grievance.save();
    
    res.json({ 
      success: true, 
      message: 'Complaint updated successfully', 
      data: grievance 
    });
  } catch (error) {
    res.status(400).json({ success: false, error: error.message });
  }
};

// DELETE - DELETE /api/grievances/:id
exports.deleteGrievance = async (req, res) => {
  try {
    const grievance = await Grievance.findById(req.params.id);
    if (!grievance) {
      return res.status(404).json({ success: false, message: 'Complaint not found' });
    }
    
    // ← ADD PERMISSION CHECK
    if (grievance.workerId !== req.workerId) {
      return res.status(403).json({ success: false, message: 'You can only delete your own complaints' });
    }
    
    await Grievance.findByIdAndDelete(req.params.id);
    res.json({ success: true, message: 'Complaint deleted successfully' });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

// ESCALATE - PUT /api/grievances/:id/escalate
exports.escalateGrievance = async (req, res) => {
  try {
    const { escalatedBy, reason } = req.body;
    const grievance = await Grievance.findById(req.params.id);
    
    if (!grievance) {
      return res.status(404).json({ success: false, message: 'Complaint not found' });
    }
    
    grievance.status = 'escalated';
    grievance.priority = 'high';
    grievance.escalatedBy = escalatedBy || 'system';
    grievance.escalatedAt = new Date();
    grievance.updatedAt = new Date();
    
    if (reason) {
      grievance.description = `[ESCALATED: ${reason}]\n${grievance.description}`;
    }
    
    await grievance.save();
    
    res.json({
      success: true,
      message: 'Complaint escalated successfully',
      grievance: {
        id: grievance._id,
        status: grievance.status,
        priority: grievance.priority,
        escalatedBy: grievance.escalatedBy,
        escalatedAt: grievance.escalatedAt
      }
    });
    
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

// BULK ESCALATE - POST /api/grievances/bulk-escalate
exports.bulkEscalate = async (req, res) => {
  try {
    const { category, escalatedBy } = req.body;
    
    const filter = { status: 'pending', category: category };
    const update = {
      status: 'escalated',
      priority: 'high',
      escalatedBy: escalatedBy || 'system',
      escalatedAt: new Date(),
      updatedAt: new Date()
    };
    
    const result = await Grievance.updateMany(filter, update);
    
    res.json({
      success: true,
      message: `${result.modifiedCount} complaints escalated`,
      escalated_count: result.modifiedCount
    });
    
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

// CLUSTER - POST /api/grievances/cluster
exports.clusterComplaints = async (req, res) => {
  try {
    const { category, days = 30 } = req.body;
    
    const dateLimit = new Date();
    dateLimit.setDate(dateLimit.getDate() - days);
    
    const filter = { createdAt: { $gte: dateLimit } };
    if (category) filter.category = category;
    
    const grievances = await Grievance.find(filter);
    
    const clusters = {};
    
    for (const grievance of grievances) {
      const key = grievance.category;
      if (!clusters[key]) {
        clusters[key] = {
          category: key,
          count: 0,
          complaints: [],
          commonTags: new Set(),
          avgPriority: 0,
          prioritySum: 0
        };
      }
      
      clusters[key].count++;
      clusters[key].complaints.push({
        id: grievance._id,
        description: grievance.description.substring(0, 100),
        status: grievance.status
      });
      
      const priorityValue = { low: 1, medium: 2, high: 3, urgent: 4 }[grievance.priority] || 1;
      clusters[key].prioritySum += priorityValue;
      
      grievance.tags.forEach(tag => clusters[key].commonTags.add(tag));
    }
    
    for (const key in clusters) {
      clusters[key].avgPriority = (clusters[key].prioritySum / clusters[key].count).toFixed(1);
      clusters[key].commonTags = Array.from(clusters[key].commonTags);
      delete clusters[key].prioritySum;
    }
    
    res.json({
      success: true,
      total_complaints: grievances.length,
      clusters: clusters,
      cluster_count: Object.keys(clusters).length
    });
    
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

// ANALYTICS - GET /api/analytics/complaints
exports.getAnalytics = async (req, res) => {
  try {
    const aggregateData = await Grievance.aggregate([
      { $group: { _id: '$category', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);
    
    const statusData = await Grievance.aggregate([
      { $group: { _id: '$status', count: { $sum: 1 } } }
    ]);
    
    const priorityData = await Grievance.aggregate([
      { $group: { _id: '$priority', count: { $sum: 1 } } }
    ]);
    
    const formattedData = {};
    aggregateData.forEach(item => {
      formattedData[item._id] = item.count;
    });
    
    const statusDistribution = {};
    statusData.forEach(item => {
      statusDistribution[item._id] = item.count;
    });
    
    const priorityDistribution = {};
    priorityData.forEach(item => {
      priorityDistribution[item._id] = item.count;
    });
    
    res.json({ 
      success: true, 
      analytics: {
        by_category: formattedData,
        by_status: statusDistribution,
        by_priority: priorityDistribution,
        total: await Grievance.countDocuments()
      }
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
};

// HEALTH CHECK - GET /api/health
exports.healthCheck = (req, res) => {
  res.json({ 
    status: 'OK', 
    service: 'Grievance Service', 
    port: process.env.PORT || 3001 
  });
};