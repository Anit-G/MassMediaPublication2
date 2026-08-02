import React, { useState, useEffect } from 'react';
import { 
  Play, 
  Square, 
  Database, 
  Tv, 
  Terminal, 
  Settings, 
  BookOpen, 
  Mic, 
  Video, 
  UploadCloud, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  Layers,
  Sparkles,
  FileCode,
  ShieldCheck,
  Cpu
} from 'lucide-react';

interface PipelineStatus {
  db_path?: string;
  total_books?: number;
  book_status?: Record<string, number>;
  total_chapters?: number;
  chapter_audio_status?: Record<string, number>;
  chapter_video_status?: Record<string, number>;
  total_shorts?: number;
  total_retries?: number;
  python_version?: string;
  error?: string;
}

interface TableData {
  columns: string[];
  rows: Record<string, any>[];
}

interface Channel {
  code: string;
  name: string;
  tag: string;
  category: string;
  voiceCodes: number[];
  channelId: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'pipeline' | 'database' | 'channels' | 'architecture'>('pipeline');
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [tables, setTables] = useState<{ name: string; count: number }[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>('ebook_list');
  const [tableData, setTableData] = useState<TableData | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  
  // Job logs state
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [selectedScript, setSelectedScript] = useState<string>('main');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Fetch status
  const fetchStatus = async () => {
    setIsRefreshing(true);
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      setStatus(data);

      const tablesRes = await fetch('/api/db/tables');
      const tablesData = await tablesRes.json();
      if (Array.isArray(tablesData)) {
        setTables(tablesData);
      }
    } catch (err) {
      console.error('Failed to fetch pipeline status:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Fetch table rows
  const fetchTableData = async (tableName: string) => {
    try {
      const res = await fetch(`/api/db/table/${tableName}`);
      const data = await res.json();
      setTableData(data);
    } catch (err) {
      console.error('Failed to fetch table data:', err);
    }
  };

  // Fetch channel specs
  const fetchChannels = async () => {
    try {
      const res = await fetch('/api/channels');
      const data = await res.json();
      if (data.channels) {
        setChannels(data.channels);
      }
    } catch (err) {
      console.error('Failed to fetch channels:', err);
    }
  };

  // Poll job logs
  useEffect(() => {
    fetchStatus();
    fetchChannels();

    const interval = setInterval(async () => {
      try {
        const res = await fetch('/api/pipeline/logs');
        const data = await res.json();
        setIsRunning(data.isRunning);
        if (data.logs && Array.isArray(data.logs)) {
          setLogs(data.logs);
        }
      } catch (e) {
        // ignore poll errors
      }
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeTab === 'database' && selectedTable) {
      fetchTableData(selectedTable);
    }
  }, [activeTab, selectedTable]);

  const handleSeedData = async () => {
    try {
      await fetch('/api/db/seed', { method: 'POST' });
      fetchStatus();
      if (selectedTable) fetchTableData(selectedTable);
    } catch (err) {
      console.error('Error seeding test data:', err);
    }
  };

  const handleRunScript = async () => {
    try {
      const res = await fetch('/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script: selectedScript })
      });
      const data = await res.json();
      if (data.error) {
        alert(data.error);
      }
    } catch (err) {
      console.error('Error starting script:', err);
    }
  };

  const handleStopScript = async () => {
    try {
      await fetch('/api/pipeline/stop', { method: 'POST' });
    } catch (err) {
      console.error('Error stopping script:', err);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navigation */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg border border-indigo-500/30">
              <Layers className="w-6 h-6" />
            </div>
            <div>
              <h1 className="font-bold text-lg text-slate-100 tracking-tight leading-none">
                Mass Media Publication
              </h1>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Automated Gutenberg → TTS → Video → Publishing Pipeline
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300 font-mono">
              <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}`} />
              {isRunning ? 'PIPELINE RUNNING' : 'PIPELINE IDLE'}
            </div>
            <button
              onClick={fetchStatus}
              disabled={isRefreshing}
              className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition"
              title="Refresh status"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      {/* Tab Controls */}
      <div className="bg-slate-900 border-b border-slate-800 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto flex space-x-8">
          <button
            onClick={() => setActiveTab('pipeline')}
            className={`py-3 text-sm font-medium border-b-2 flex items-center gap-2 transition ${
              activeTab === 'pipeline'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Play className="w-4 h-4" /> Pipeline Control
          </button>
          <button
            onClick={() => setActiveTab('database')}
            className={`py-3 text-sm font-medium border-b-2 flex items-center gap-2 transition ${
              activeTab === 'database'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Database className="w-4 h-4" /> State & DB Explorer
          </button>
          <button
            onClick={() => setActiveTab('channels')}
            className={`py-3 text-sm font-medium border-b-2 flex items-center gap-2 transition ${
              activeTab === 'channels'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Tv className="w-4 h-4" /> YouTube Channels
          </button>
          <button
            onClick={() => setActiveTab('architecture')}
            className={`py-3 text-sm font-medium border-b-2 flex items-center gap-2 transition ${
              activeTab === 'architecture'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <ShieldCheck className="w-4 h-4" /> Architecture & Plan
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {activeTab === 'pipeline' && (
          <div className="space-y-6">
            {/* Quick Metrics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center gap-4">
                <div className="p-3 bg-blue-500/10 text-blue-400 rounded-lg">
                  <BookOpen className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Ebooks</p>
                  <p className="text-2xl font-bold text-slate-100">{status?.total_books ?? 0}</p>
                </div>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center gap-4">
                <div className="p-3 bg-purple-500/10 text-purple-400 rounded-lg">
                  <Mic className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Audio Chapters</p>
                  <p className="text-2xl font-bold text-slate-100">{status?.total_chapters ?? 0}</p>
                </div>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center gap-4">
                <div className="p-3 bg-indigo-500/10 text-indigo-400 rounded-lg">
                  <Video className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Shorts Items</p>
                  <p className="text-2xl font-bold text-slate-100">{status?.total_shorts ?? 0}</p>
                </div>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center gap-4">
                <div className="p-3 bg-amber-500/10 text-amber-400 rounded-lg">
                  <AlertCircle className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Retries Tracked</p>
                  <p className="text-2xl font-bold text-slate-100">{status?.total_retries ?? 0}</p>
                </div>
              </div>
            </div>

            {/* Pipeline Stage Architecture Flow */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="text-base font-semibold text-slate-200 mb-4 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-400" /> Automated Pipeline Workflow Stages
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 relative">
                {/* Stage 1 */}
                <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 relative">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-indigo-400 font-mono">STAGE 1</span>
                    <BookOpen className="w-4 h-4 text-slate-500" />
                  </div>
                  <h3 className="text-sm font-medium text-slate-200">Gutenberg Scraper</h3>
                  <p className="text-xs text-slate-400 mt-1">Parses metadata & chapter JSON structures.</p>
                  <div className="mt-3 text-[11px] font-mono text-slate-500 bg-slate-900 p-2 rounded">
                    PARSABLE → PARSED
                  </div>
                </div>

                {/* Stage 2 */}
                <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 relative">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-indigo-400 font-mono">STAGE 2</span>
                    <Mic className="w-4 h-4 text-slate-500" />
                  </div>
                  <h3 className="text-sm font-medium text-slate-200">Kokoro TTS Engine</h3>
                  <p className="text-xs text-slate-400 mt-1">Generates chapter audio & shorts WAV files.</p>
                  <div className="mt-3 text-[11px] font-mono text-slate-500 bg-slate-900 p-2 rounded">
                    PARSED → AUDGEN_DONE
                  </div>
                </div>

                {/* Stage 3 */}
                <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 relative">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-indigo-400 font-mono">STAGE 3</span>
                    <Video className="w-4 h-4 text-slate-500" />
                  </div>
                  <h3 className="text-sm font-medium text-slate-200">FFmpeg Video Gen</h3>
                  <p className="text-xs text-slate-400 mt-1">Assembles background visual, audio & waveform.</p>
                  <div className="mt-3 text-[11px] font-mono text-slate-500 bg-slate-900 p-2 rounded">
                    AUDGEN_DONE → VIDGEN_DONE
                  </div>
                </div>

                {/* Stage 4 */}
                <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 relative">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-indigo-400 font-mono">STAGE 4</span>
                    <UploadCloud className="w-4 h-4 text-slate-500" />
                  </div>
                  <h3 className="text-sm font-medium text-slate-200">Publish & Upload</h3>
                  <p className="text-xs text-slate-400 mt-1">Uploads finished videos to YouTube channels.</p>
                  <div className="mt-3 text-[11px] font-mono text-slate-500 bg-slate-900 p-2 rounded">
                    VIDGEN_DONE → PUBLISHED
                  </div>
                </div>
              </div>
            </div>

            {/* Execution Controls */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                <div>
                  <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
                    <Terminal className="w-5 h-5 text-indigo-400" /> Pipeline Execution Console
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Trigger main pipeline, worker tasks, or test pipeline runs cleanly.
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <select
                    value={selectedScript}
                    onChange={(e) => setSelectedScript(e.target.value)}
                    disabled={isRunning}
                    className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:border-indigo-500"
                  >
                    <option value="main">Full Main Pipeline (main_pipeline.py)</option>
                    <option value="test">Test Pipeline Runner (test_pipeline.py)</option>
                    <option value="tts">TTS Generator (TTS/TTS.py)</option>
                    <option value="video">Video Generator (VideoGen/VideoGenerator.py)</option>
                    <option value="scrapper">Chapter Parser (Scrapper/Parser/ParseChapters.py)</option>
                  </select>

                  {!isRunning ? (
                    <button
                      onClick={handleRunScript}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 transition shadow-lg shadow-indigo-600/20"
                    >
                      <Play className="w-3.5 h-3.5" /> Execute Task
                    </button>
                  ) : (
                    <button
                      onClick={handleStopScript}
                      className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 transition shadow-lg shadow-rose-600/20"
                    >
                      <Square className="w-3.5 h-3.5" /> Stop Process
                    </button>
                  )}

                  <button
                    onClick={handleSeedData}
                    className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition"
                    title="Seed sample data if DB is empty"
                  >
                    Seed Sample DB
                  </button>
                </div>
              </div>

              {/* Log Window */}
              <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 font-mono text-xs text-slate-300 h-80 overflow-y-auto space-y-1">
                {logs.length === 0 ? (
                  <div className="text-slate-600 italic py-10 text-center">
                    No active output. Click "Execute Task" to launch a pipeline run or seed test data.
                  </div>
                ) : (
                  logs.map((line, idx) => (
                    <div key={idx} className="whitespace-pre-wrap leading-relaxed border-b border-slate-900/40 pb-0.5">
                      {line}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'database' && (
          <div className="space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                  <Database className="w-5 h-5 text-indigo-400" /> Pipeline Database State
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  SQLite Database: <code className="text-indigo-300 font-mono">{status?.db_path || 'Data/testDB.db3'}</code>
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleSeedData}
                  className="px-3 py-1.5 bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600/30 rounded-lg text-xs font-medium transition"
                >
                  Populate Sample Data
                </button>
              </div>
            </div>

            {/* Table Selector */}
            <div className="flex gap-2 border-b border-slate-800 pb-2">
              {tables.map((t) => (
                <button
                  key={t.name}
                  onClick={() => setSelectedTable(t.name)}
                  className={`px-3 py-1.5 text-xs font-mono rounded-lg transition flex items-center gap-2 ${
                    selectedTable === t.name
                      ? 'bg-indigo-600 text-white font-medium'
                      : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                  }`}
                >
                  <span>{t.name}</span>
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-slate-800 text-slate-300">
                    {t.count}
                  </span>
                </button>
              ))}
            </div>

            {/* Data Table */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              {!tableData || tableData.rows.length === 0 ? (
                <div className="p-12 text-center text-slate-500 text-xs">
                  No records in table <code className="text-slate-400">{selectedTable}</code>. Click "Populate Sample Data" to insert sample ebooks and chapter states.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-950 text-slate-400 uppercase font-mono text-[10px] tracking-wider border-b border-slate-800">
                      <tr>
                        {tableData.columns.map((col) => (
                          <th key={col} className="px-4 py-3 font-semibold">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                      {tableData.rows.map((row, idx) => (
                        <tr key={idx} className="hover:bg-slate-800/30 transition">
                          {tableData.columns.map((col) => (
                            <td key={col} className="px-4 py-3 max-w-xs truncate">
                              {col === 'status' || col.includes('status') ? (
                                <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                  row[col] === 'PARSED' || row[col] === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-400' :
                                  row[col] === 'AUDGEN_DONE' || row[col] === 'VIDGEN_DONE' ? 'bg-indigo-500/20 text-indigo-300' :
                                  row[col] === 'GENERATING' ? 'bg-amber-500/20 text-amber-300' :
                                  'bg-slate-800 text-slate-400'
                                }`}>
                                  {String(row[col])}
                                </span>
                              ) : (
                                String(row[col] ?? '-')
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'channels' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <Tv className="w-5 h-5 text-indigo-400" /> YouTube Channels & Voice Specs
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Configured YouTube publishing channels, categories, and Kokoro voice mappings.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {channels.map((ch) => (
                <div key={ch.code} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="px-2 py-0.5 bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 rounded text-[10px] font-mono font-bold">
                        {ch.code}
                      </span>
                      <h3 className="text-base font-bold text-slate-100 mt-1">{ch.name}</h3>
                      <p className="text-xs text-indigo-400 font-mono">{ch.tag}</p>
                    </div>
                    <span className="text-xs text-slate-400 bg-slate-950 px-2.5 py-1 rounded-full border border-slate-800">
                      {ch.category}
                    </span>
                  </div>

                  <div className="border-t border-slate-800/80 pt-3 flex items-center justify-between text-xs font-mono text-slate-400">
                    <div>
                      <span className="text-slate-500">Voice Codes: </span>
                      <span className="text-slate-200">[{ch.voiceCodes.join(', ')}]</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Channel ID: </span>
                      <span className="text-slate-300">{ch.channelId.substring(0, 10)}...</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'architecture' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-indigo-400" /> Architecture & Plan Verification
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Compliance with user-specified architectural constraints.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  <h3 className="font-semibold text-slate-200 text-sm">Singleton SQLite Data Access</h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Configured for single-thread batch/cron pipeline usage with safe connection handling, keeping the existing database operations clean and lightweight.
                </p>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  <h3 className="font-semibold text-slate-200 text-sm">Preserved CLI FFmpeg Execution</h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  CLI subprocess invocations are maintained directly as requested, providing full capabilities for audio-visual video generation and waveform synthesis.
                </p>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  <h3 className="font-semibold text-slate-200 text-sm">Graceful AES Key Handling</h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Updated secret handling logic to throw clear exceptions instead of calling <code className="text-indigo-300 font-mono">os.abort()</code>, keeping the server resilient.
                </p>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  <h3 className="font-semibold text-slate-200 text-sm">Web Control Center Integration</h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Full-stack Express + React application running on port 3000 to monitor, seed, run, and inspect the entire pipeline.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
