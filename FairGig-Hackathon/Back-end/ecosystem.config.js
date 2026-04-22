// ecosystem.config.js - Fixed (No extra windows)
module.exports = {
  apps: [
    {
      name: 'fairgig-grievance',
      script: 'node',
      args: 'index.js',
      cwd: './fairgig-node',
      env: {
        NODE_ENV: 'production',
        PORT: 3001
      },
      error_file: './logs/grievance-error.log',
      out_file: './logs/grievance-out.log',
      autorestart: true,
      watch: false
    },
    {
      name: 'fairgig-auth',
      script: 'python',
      args: 'main.py',
      cwd: './fairgig-python',
      interpreter: 'python',
      env: {
        PORT: 8000
      },
      error_file: './logs/auth-error.log',
      out_file: './logs/auth-out.log',
      autorestart: true,
      watch: false
    },
    {
      name: 'fairgig-anomaly',
      script: 'python',
      args: 'anomaly.py',
      cwd: './fairgig-python',
      interpreter: 'python',
      env: {
        PORT: 8001
      },
      error_file: './logs/anomaly-error.log',
      out_file: './logs/anomaly-out.log',
      autorestart: true,
      watch: false
    },
    {
      name: 'fairgig-certificate',
      script: 'python',
      args: 'certificate.py',
      cwd: './certificate-service',
      interpreter: 'python',
      env: {
        PORT: 8002
      },
      error_file: './logs/certificate-error.log',
      out_file: './logs/certificate-out.log',
      autorestart: true,
      watch: false
    }
  ]
};