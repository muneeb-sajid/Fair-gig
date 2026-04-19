// src/config/database.js
const mongoose = require('mongoose');

const connectDB = async () => {
    try {
        await mongoose.connect(process.env.MONGODB_URI);
        console.log('✅ MongoDB Connected for Grievance Service');
    } catch (error) {
        console.error('❌ MongoDB Error:', error.message);
        process.exit(1);
    }
};

module.exports = connectDB;