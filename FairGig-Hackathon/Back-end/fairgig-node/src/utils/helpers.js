// src/utils/helpers.js

// Auto-tag complaints based on keywords
function autoTag(description, category) {
  // Safety check - if inputs are undefined or null
  if (!description || !category) {
    return [];
  }
  
  const tags = [category.toLowerCase()];
  
  const keywordMap = {
    'deactivation': ['deactivated', 'banned', 'suspended', 'blocked'],
    'payment': ['payment', 'paid', 'money', 'salary', 'earnings'],
    'commission': ['commission', 'deduction', 'fee', 'charge'],
    'support': ['support', 'help', 'assistance', 'customer service'],
    'app': ['app', 'application', 'crash', 'bug', 'error'],
    'rating': ['rating', 'review', 'star', 'feedback']
  };
  
  const lowerDesc = description.toLowerCase();
  for (const [tag, keywords] of Object.entries(keywordMap)) {
    if (keywords.some(k => lowerDesc.includes(k))) {
      tags.push(tag);
    }
  }
  
  return [...new Set(tags)];
}

// Calculate priority based on description and category
function calculatePriority(description, category) {
  // Safety check - if description is undefined or null
  if (!description) {
    return 'low';
  }
  
  const lowerDesc = description.toLowerCase();
  
  if (lowerDesc.includes('urgent') || lowerDesc.includes('emergency') || 
      lowerDesc.includes('immediate') || (category && category === 'Urgent')) {
    return 'urgent';
  }
  if (lowerDesc.includes('high') || lowerDesc.includes('serious') || 
      lowerDesc.includes('critical')) {
    return 'high';
  }
  if (lowerDesc.includes('medium')) {
    return 'medium';
  }
  return 'low';
}

module.exports = { autoTag, calculatePriority };