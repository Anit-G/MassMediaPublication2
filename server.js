import express from 'express';
import cors from 'cors';
import { exec, spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

// Helper to run python commands
function runPythonBridge(args) {
  return new Promise((resolve) => {
    const py = spawn('python3', ['Scripts/api_bridge.py', ...args], { cwd: __dirname });
    let stdout = '';
    let stderr = '';

    py.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    py.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    py.on('close', (code) => {
      if (code !== 0 && !stdout) {
        return resolve({ error: `Process exited with code ${code}`, stderr });
      }
      try {
        const json = JSON.parse(stdout.trim());
        resolve(json);
      } catch (e) {
        resolve({ raw: stdout, stderr });
      }
    });
  });
}

// API Routes
app.get('/api/status', async (req, res) => {
  const result = await runPythonBridge(['status']);
  res.json(result);
});

app.get('/api/channel-status', async (req, res) => {
  const result = await runPythonBridge(['channel_status']);
  res.json(result);
});

app.get('/api/db/tables', async (req, res) => {
  const result = await runPythonBridge(['tables']);
  res.json(result);
});

app.get('/api/db/table/:name', async (req, res) => {
  const tableName = req.params.name;
  const limit = req.query.limit || 50;
  const result = await runPythonBridge(['table', tableName, limit]);
  res.json(result);
});

app.post('/api/db/seed', async (req, res) => {
  const result = await runPythonBridge(['seed']);
  res.json(result);
});

app.post('/api/pipeline/reset-chapter', async (req, res) => {
  const { ebook_no, voice_code, chapter_idx, stage } = req.body;
  if (!ebook_no || !voice_code || chapter_idx === undefined) {
    return res.status(400).json({ error: 'Missing ebook_no, voice_code, or chapter_idx' });
  }
  const args = ['reset_chapter', ebook_no, voice_code, chapter_idx];
  if (stage) args.push(stage);
  const result = await runPythonBridge(args);
  res.json(result);
});

app.post('/api/pipeline/reset-book', async (req, res) => {
  const { ebook_no } = req.body;
  if (!ebook_no) {
    return res.status(400).json({ error: 'Missing ebook_no' });
  }
  const result = await runPythonBridge(['reset_book', ebook_no]);
  res.json(result);
});

app.get('/api/youtube/tokens/status', async (req, res) => {
  const result = await runPythonBridge(['youtube_tokens_status']);
  res.json(result);
});

app.post('/api/youtube/tokens/refresh', async (req, res) => {
  const { force = false, interactive = false } = req.body || {};
  const result = await runPythonBridge(['refresh_youtube_tokens', force ? 'true' : 'false', interactive ? 'true' : 'false']);
  res.json(result);
});

app.post('/api/youtube/client-secret', async (req, res) => {
  const { secret } = req.body;
  if (!secret) {
    return res.status(400).json({ error: 'Missing secret payload' });
  }
  const secretStr = typeof secret === 'string' ? secret : JSON.stringify(secret);
  const result = await runPythonBridge(['set_client_secret', secretStr]);
  res.json(result);
});

app.post('/api/youtube/token/:channelId', async (req, res) => {
  const { channelId } = req.params;
  const { token } = req.body;
  if (!channelId || !token) {
    return res.status(400).json({ error: 'Missing channelId or token payload' });
  }
  const tokenStr = typeof token === 'string' ? token : JSON.stringify(token);
  const result = await runPythonBridge(['set_channel_token', channelId, tokenStr]);
  res.json(result);
});

app.get('/api/channels', (req, res) => {
  const channelFile = path.join(__dirname, 'Data/Channel Specs/Channel Names and Descriptions.txt');
  let textContent = '';
  if (fs.existsSync(channelFile)) {
    textContent = fs.readFileSync(channelFile, 'utf-8');
  }

  const channels = [
    {
      code: 'RS',
      name: "Echo's Slumber",
      tag: '@EchoSlumber',
      category: 'Relaxing and Soothing',
      voiceCodes: [3, 7],
      channelId: 'UCXeqq2XcvF7jjEcv35dPl8A',
      watermark: '/Data/Channel Specs/erbuesechoes channel watermark.png'
    },
    {
      code: 'MS',
      name: 'Erebus Echoes',
      tag: '@ErebosEchoes',
      category: 'Mystery and Suspense',
      voiceCodes: [18, 26],
      channelId: 'UCfOw-0ovjVZSE8HvaCNJJ_Q',
      watermark: '/Data/Channel Specs/marrormanuscripts channel watermark.png'
    },
    {
      code: 'WE',
      name: 'MoonBerry Echoes',
      tag: '@MoonBerryEchoes',
      category: 'Whimsical Escapism',
      voiceCodes: [20, 23],
      channelId: 'UCKpi4fdhxKbO_DWUD3FODTA',
      watermark: '/Data/Channel Specs/moonberryechoes channel watermark.png'
    },
    {
      code: 'LM',
      name: 'Marrow & Manuscripts',
      tag: '@MarrowManuscripts',
      category: 'Literary Masterpieces',
      voiceCodes: [17, 22],
      channelId: 'UChDu5fX4ICAQSgdT653TGzA',
      watermark: '/Data/Channel Specs/orpheusodes channel watermark.png'
    },
    {
      code: 'TA',
      name: 'Orpheus Odes',
      tag: '@OrpheusOdes',
      category: 'Thrilling and Adventurous',
      voiceCodes: [15, 19],
      channelId: 'UCGKLnKX4AF6r1Fz86BvUPEw',
      banner: '/Data/Channel Specs/erebusechoes channel banner.jpg'
    }
  ];

  res.json({ channels, details: textContent });
});

app.get('/api/logs', (req, res) => {
  const logDir = path.join(__dirname, 'Central_Logs');
  let logs = [];
  if (fs.existsSync(logDir)) {
    const files = fs.readdirSync(logDir);
    files.forEach((file) => {
      const filePath = path.join(logDir, file);
      if (fs.statSync(filePath).isFile()) {
        const content = fs.readFileSync(filePath, 'utf-8');
        logs.push({ file, lines: content.split('\n').slice(-100) });
      }
    });
  }
  res.json({ logs });
});

// Run script API endpoint (streams logs)
let activeProcess = null;
let activeLogOutput = [];

app.post('/api/pipeline/run', (req, res) => {
  const { script } = req.body;
  
  if (activeProcess) {
    return res.status(400).json({ error: 'A pipeline job is already running', pid: activeProcess.pid });
  }

  let targetScript = 'main_pipeline.py';
  if (script === 'test') targetScript = 'test_pipeline.py';
  else if (script === 'tts') targetScript = 'TTS/TTS.py';
  else if (script === 'video') targetScript = 'VideoGen/VideoGenerator.py';
  else if (script === 'scrapper') targetScript = 'Scrapper/Parser/ParseChapters.py';

  activeLogOutput = [`[INIT] Starting ${targetScript}...` ];

  activeProcess = spawn('python3', [targetScript], { cwd: __dirname });

  activeProcess.stdout.on('data', (data) => {
    const str = data.toString();
    activeLogOutput.push(str);
    if (activeLogOutput.length > 500) activeLogOutput.shift();
  });

  activeProcess.stderr.on('data', (data) => {
    const str = data.toString();
    activeLogOutput.push(`[STDERR] ${str}`);
    if (activeLogOutput.length > 500) activeLogOutput.shift();
  });

  activeProcess.on('close', (code) => {
    activeLogOutput.push(`[FINISHED] Process exited with code ${code}`);
    activeProcess = null;
  });

  res.json({ message: `Started ${targetScript}`, pid: activeProcess.pid });
});

app.get('/api/pipeline/logs', (req, res) => {
  res.json({
    isRunning: !!activeProcess,
    pid: activeProcess ? activeProcess.pid : null,
    logs: activeLogOutput
  });
});

app.post('/api/pipeline/stop', (req, res) => {
  if (activeProcess) {
    activeProcess.kill('SIGTERM');
    activeProcess = null;
    activeLogOutput.push('[STOPPED] Job terminated by user');
    return res.json({ message: 'Job terminated' });
  }
  res.json({ message: 'No running job' });
});

// Serve Vite static files or proxy to Vite dev server
const isProduction = fs.existsSync(path.join(__dirname, 'dist'));
if (isProduction) {
  app.use(express.static(path.join(__dirname, 'dist')));
  app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'dist', 'index.html'));
  });
} else {
  // In dev mode when Vite hasn't pre-built, serve index.html or fallback
  app.use(express.static(path.join(__dirname, 'public')));
  
  // Basic middleware to build client dynamically with vite if needed, or express static fallback
  app.get('*', (req, res) => {
    if (fs.existsSync(path.join(__dirname, 'dist/index.html'))) {
      res.sendFile(path.join(__dirname, 'dist/index.html'));
    } else {
      res.send(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>Mass Media Publication Pipeline Server</title>
          <style>
            body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }
            .card { background: #1e293b; padding: 1.5rem; border-radius: 8px; border: 1px solid #334155; }
            a { color: #38bdf8; }
          </style>
        </head>
        <body>
          <div class="card">
            <h2>Mass Media Publication Pipeline Server</h2>
            <p>Server is running on port 3000!</p>
            <p>Please build client assets with <code>npm run build</code> or view the REST API endpoints.</p>
          </div>
        </body>
        </html>
      `);
    }
  });
}

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Mass Media Publication Server listening on http://0.0.0.0:${PORT}`);
});
