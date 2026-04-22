"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { Activity, Clock, PlayCircle, AlertCircle, CheckCircle2 } from "lucide-react";
import { ApiClient, ExecutionSummary } from "@/lib/api";

const StatusBadge = ({ status }: { status: string }) => {
  const styles: Record<string, string> = {
    PENDING: "bg-gray-500/10 text-gray-400 border-gray-500/20",
    RUNNING: "bg-blue-500/10 text-blue-400 border-blue-500/20 shadow-[0_0_10px_rgba(59,130,246,0.1)]",
    PAUSED: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    COMPLETED: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    FAILED: "bg-red-500/10 text-red-400 border-red-500/20",
    TERMINATED: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  };

  const icons: Record<string, any> = {
    RUNNING: <Activity className="w-3 h-3 mr-1.5 animate-pulse" />,
    COMPLETED: <CheckCircle2 className="w-3 h-3 mr-1.5" />,
    FAILED: <AlertCircle className="w-3 h-3 mr-1.5" />,
  };

  const css = styles[status] || styles.PENDING;

  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${css}`}>
      {icons[status] || <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5 opacity-60" />}
      {status}
    </span>
  );
};

export default function ExecutionsDashboard() {
  const [executions, setExecutions] = useState<ExecutionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchExecutions = async () => {
    try {
      const data = await ApiClient.getExecutions();
      setExecutions(data);
    } catch (err) {
      console.error("Failed to load executions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExecutions();
    const interval = setInterval(fetchExecutions, 3000); // Poll every 3 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Execution History</h1>
          <p className="text-gray-400 mt-1">Monitor all workflow runs in real-time.</p>
        </div>
        <Link 
          href="/templates" 
          className="bg-primary hover:bg-primary-hover text-white px-4 py-2 rounded-lg font-medium transition-colors shadow-lg shadow-blue-500/20 flex items-center"
        >
          <PlayCircle className="w-4 h-4 mr-2" />
          Trigger New
        </Link>
      </div>

      <div className="glass rounded-xl overflow-hidden border border-card-border">
        {loading ? (
          <div className="p-12 text-center text-gray-500 flex flex-col items-center">
            <Activity className="w-8 h-8 animate-pulse mb-4 text-blue-500" />
            Loading executions...
          </div>
        ) : executions.length === 0 ? (
          <div className="p-12 text-center text-gray-500">
            <p>No executions found.</p>
            <Link href="/templates" className="text-blue-400 hover:underline mt-2 inline-block">Go trigger one!</Link>
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-card-border bg-black/20 text-xs uppercase tracking-wider text-gray-400 font-semibold">
                <th className="p-4 pl-6">Execution ID</th>
                <th className="p-4">Template ID</th>
                <th className="p-4">Status</th>
                <th className="p-4">Started</th>
                <th className="p-4">Last Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-card-border">
              {executions.map((exec) => (
                <tr key={exec.execution_id} className="glass-hover group">
                  <td className="p-4 pl-6">
                    <Link 
                      href={`/executions/${exec.execution_id}`}
                      className="font-mono text-sm text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      {exec.execution_id.split("-")[0]}...{exec.execution_id.split("-")[4]}
                    </Link>
                  </td>
                  <td className="p-4">
                    <span className="font-mono text-xs text-gray-400 bg-black/30 px-2 py-1 rounded">
                      {exec.template_id.substring(0, 8)}
                    </span>
                  </td>
                  <td className="p-4">
                    <StatusBadge status={exec.status} />
                  </td>
                  <td className="p-4 text-sm text-gray-400 flex items-center mt-1.5">
                    <Clock className="w-3 h-3 mr-1.5 opacity-50" />
                    {formatDistanceToNow(new Date(exec.created_at), { addSuffix: true })}
                  </td>
                  <td className="p-4 text-sm text-gray-500">
                    {new Date(exec.updated_at).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
