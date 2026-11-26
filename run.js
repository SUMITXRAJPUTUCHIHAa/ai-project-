const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const customPython = path.resolve('C:/Users/sumit/.gemini/antigravity/scratch/python311/python.exe');
const pythonCmd = fs.existsSync(customPython) ? customPython : 'python';

console.log('==============================================================');
console.log('  LPU Admission Intelligence Portal (UMS 2024-25 Edition)');
console.log('  AI Model: Groq Cloud (openai/gpt-oss-120b)');
console.log('  Starting server at http://localhost:8080');
console.log('==============================================================');

const child = spawn(pythonCmd, ['app.py'], {
  cwd: __dirname,
  stdio: 'inherit',
  shell: true
});

child.on('error', (err) => {
  console.error('Failed to start server:', err);
});

child.on('close', (code) => {
  process.exit(code || 0);
});

