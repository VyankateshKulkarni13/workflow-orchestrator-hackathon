"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { ApiClient, ExecutionDetail, WorkflowTemplate } from "@/lib/api";
import { WorkflowGraph } from "@/components/WorkflowGraph";
import { 
  Play, Pause, Square, AlertTriangle, Check, 
  TerminalSquare, Clock, FileJson, ArrowLeft
} from "lucide-react";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";

export default function ExecutionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const executionId = resolvedParams.id;
  const router = useRouter();

  const [execution, setExecution] = useState<ExecutionDetail | null>(null);
  const [template, setTemplate] = useState<WorkflowTemplate | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  // Poll execution status
  useEffect(() => {
    let isMounted = true;
    
    const fetchExecution = async () => {
      try {
        const data = await ApiClient.getExecution(executionId);
        if (isMounted) {
          setExecution(data);
          
          // Fetch template only once
          if (!template && data.template_id) {
            const tmpl = await ApiClient.getTemplate(data.template_id);
            setTemplate(tmpl);
          }
        }
      } catch (err) {
        console.error("Failed to fetch execution:", err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchExecution();
    const interval = setInterval(fetchExecution, 1500); // Poll every 1.5s
    
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [executionId, template]);

  // Controls Handlers
  const handlePause = async () => {
    await ApiClient.pauseExecution(executionId);
  };
  const handleResume = async () => {
    await ApiClient.resumeExecution(executionId);
  };
  const handleTerminate = async () => {
    if (confirm("Are you sure you want to hard terminate this workflow?")) {
      await ApiClient.terminateExecution(executionId);
    }
  };

  const handleApprove = async (taskId: string) => {
    try {
      await ApiClient.approveTask(taskId, { comment: "Approved via Dashboard" });
    } catch (err) {
      alert("Failed to approve task");
    }
  };

  if (loading || !execution || !template) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  const selectedTask = execution.tasks.find((t) => t.task_id === selectedTaskId) || execution.tasks[0];
  const isPaused = execution.status === "PAUSED";
  const isTerminal = ["COMPLETED", "FAILED", "TERMINATED"].includes(execution.status);

  // Check if any task is AWAITING_APPROVAL
  const approvalTask = execution.tasks.find(t => t.status === "AWAITING_APPROVAL");

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col space-y-4 max-w-7xl mx-auto">
      {/* Header Bar */}
      <div className="flex items-center justify-between glass px-6 py-4 rounded-xl border border-card-border">
        <div className="flex items-center space-x-4">
          <Link href="/" className="text-gray-400 hover:text-white transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-xl font-bold text-gray-100">{template.name}</h1>
              <span className={`px-2.5 py-1 rounded-full text-xs font-semibold uppercase ${
                execution.status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                execution.status === 'FAILED' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                execution.status === 'PAUSED' ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20' :
                'bg-blue-500/10 text-blue-400 border border-blue-500/20 animate-pulse'
              }`}>
                {execution.status}
              </span>
            </div>
            <p className="text-xs text-gray-400 font-mono mt-1">ID: {execution.execution_id}</p>
          </div>
        </div>

        {/* Global Controls */}
        <div className="flex items-center space-x-3">
          {!isTerminal && (
            <>
              {isPaused ? (
                <button onClick={handleResume} className="btn-control bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                  <Play className="w-4 h-4 mr-2" /> Resume
                </button>
              ) : (
                <button onClick={handlePause} className="btn-control bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                  <Pause className="w-4 h-4 mr-2" /> Pause
                </button>
              )}
              <button onClick={handleTerminate} className="btn-control bg-red-500/10 hover:bg-red-500/20 text-red-400 border-red-500/30">
                <Square className="w-4 h-4 mr-2" /> Terminate
              </button>
            </>
          )}
        </div>
      </div>

      {/* Human Approval Alert */}
      {approvalTask && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 flex items-center justify-between shadow-[0_0_20px_rgba(245,158,11,0.15)]">
          <div className="flex items-center space-x-4">
            <div className="p-3 bg-yellow-500/20 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-yellow-400 animate-pulse" />
            </div>
            <div>
              <h3 className="font-bold text-yellow-400 text-lg">Human Approval Required</h3>
              <p className="text-sm text-yellow-400/80">
                Task <span className="font-mono font-semibold text-yellow-200">{approvalTask.node_id}</span> is halted and waiting for your review.
              </p>
            </div>
          </div>
          <button 
            onClick={() => handleApprove(approvalTask.task_id)}
            className="bg-yellow-400 hover:bg-yellow-500 text-yellow-950 px-6 py-2 rounded-lg font-bold transition-colors flex items-center shadow-lg"
          >
            <Check className="w-5 h-5 mr-2" />
            Approve & Continue
          </button>
        </div>
      )}

      {/* Main Content Split */}
      <div className="flex-1 flex space-x-4 min-h-0">
        
        {/* Left: Interactive DAG Graph */}
        <div className="flex-[2] glass rounded-xl border border-card-border flex flex-col p-2">
          <WorkflowGraph 
            tasks={execution.tasks} 
            dependencies={template.definition.tasks.map((t: any) => ({ 
              id: t.id, 
              depends_on: t.depends_on || [] 
            }))} 
          />
        </div>

        {/* Right: Task Details Panel */}
        <div className="flex-1 glass rounded-xl border border-card-border flex flex-col overflow-hidden">
          <div className="p-4 border-b border-card-border bg-black/20">
            <h3 className="font-semibold text-gray-100 flex items-center">
              <TerminalSquare className="w-4 h-4 mr-2 text-blue-400" />
              Task Details
            </h3>
            <p className="text-xs text-gray-500 mt-1">Select a node to view logs</p>
          </div>
          
          {/* Task Selector Tabs */}
          <div className="flex overflow-x-auto border-b border-card-border scrollbar-hide">
            {execution.tasks.map((t) => (
              <button
                key={t.task_id}
                onClick={() => setSelectedTaskId(t.task_id)}
                className={`px-4 py-3 text-xs font-medium border-b-2 whitespace-nowrap transition-colors ${
                  (selectedTask?.task_id === t.task_id) 
                    ? "border-blue-500 text-blue-400 bg-blue-500/5" 
                    : "border-transparent text-gray-500 hover:text-gray-300 hover:bg-white/5"
                }`}
              >
                {t.node_id}
              </button>
            ))}
          </div>

          {/* Task Info Body */}
          {selectedTask && (
            <div className="p-4 flex-1 overflow-y-auto space-y-6">
              
              {/* Meta */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-black/20 p-3 rounded-lg border border-card-border">
                  <span className="block text-xs text-gray-500 mb-1">Status</span>
                  <span className={`font-semibold text-sm ${
                    selectedTask.status === 'COMPLETED' ? 'text-emerald-400' :
                    selectedTask.status === 'FAILED' ? 'text-red-400' :
                    selectedTask.status === 'IN_PROGRESS' ? 'text-blue-400 animate-pulse' :
                    'text-gray-400'
                  }`}>{selectedTask.status}</span>
                </div>
                <div className="bg-black/20 p-3 rounded-lg border border-card-border">
                  <span className="block text-xs text-gray-500 mb-1">Started</span>
                  <span className="font-mono text-xs text-gray-300 flex items-center">
                    <Clock className="w-3 h-3 mr-1 opacity-50" />
                    {selectedTask.started_at ? formatDistanceToNow(new Date(selectedTask.started_at), { addSuffix: true }) : '-'}
                  </span>
                </div>
              </div>

              {/* Logs */}
              <div>
                <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 flex items-center">
                  <TerminalSquare className="w-3 h-3 mr-1.5" /> Runtime Logs
                </h4>
                <div className="bg-[#0a0a0c] border border-card-border rounded-lg p-3 overflow-x-auto">
                  <pre className="text-[11px] font-mono text-gray-400 whitespace-pre-wrap leading-relaxed">
                    {selectedTask.logs || "No logs generated yet."}
                  </pre>
                </div>
              </div>

              {/* Output Payload */}
              <div>
                <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 flex items-center">
                  <FileJson className="w-3 h-3 mr-1.5" /> Output Payload
                </h4>
                <div className="bg-[#0a0a0c] border border-card-border rounded-lg p-3 overflow-x-auto">
                  <pre className="text-[11px] font-mono text-emerald-400/80 whitespace-pre-wrap">
                    {selectedTask.output ? JSON.stringify(selectedTask.output, null, 2) : "{}"}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .btn-control {
          @apply px-4 py-2 rounded-lg font-medium transition-colors border flex items-center shadow-lg text-sm;
        }
      `}</style>
    </div>
  );
}
