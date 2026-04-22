"use client";

import { useMemo } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  Handle,
  Position,
  NodeProps,
  Edge,
  Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Activity, CheckCircle2, Clock, AlertCircle, AlertTriangle, XCircle } from "lucide-react";

// ---------------------------------------------------------------------------
// Custom Node Design
// ---------------------------------------------------------------------------
const CustomTaskNode = ({ data }: NodeProps) => {
  const { label, status } = data;

  // Status-based styling
  const config = useMemo(() => {
    switch (status) {
      case "COMPLETED":
        return {
          border: "border-emerald-500/50",
          bg: "bg-emerald-500/10",
          icon: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
          text: "text-emerald-400",
        };
      case "IN_PROGRESS":
        return {
          border: "border-blue-500/50 shadow-[0_0_15px_rgba(59,130,246,0.3)]",
          bg: "bg-blue-500/10",
          icon: <Activity className="w-5 h-5 text-blue-400 animate-pulse" />,
          text: "text-blue-400",
        };
      case "AWAITING_APPROVAL":
        return {
          border: "border-yellow-500/50 shadow-[0_0_15px_rgba(245,158,11,0.3)]",
          bg: "bg-yellow-500/10",
          icon: <AlertTriangle className="w-5 h-5 text-yellow-400 animate-bounce" />,
          text: "text-yellow-400",
        };
      case "FAILED":
        return {
          border: "border-red-500/50",
          bg: "bg-red-500/10",
          icon: <AlertCircle className="w-5 h-5 text-red-400" />,
          text: "text-red-400",
        };
      case "TERMINATED":
        return {
          border: "border-purple-500/50",
          bg: "bg-purple-500/10",
          icon: <XCircle className="w-5 h-5 text-purple-400" />,
          text: "text-purple-400 opacity-60",
        };
      default: // PENDING
        return {
          border: "border-gray-500/30",
          bg: "bg-black/40",
          icon: <Clock className="w-5 h-5 text-gray-500" />,
          text: "text-gray-400",
        };
    }
  }, [status]);

  return (
    <div className={`px-4 py-3 rounded-xl border ${config.border} ${config.bg} backdrop-blur-md min-w-[200px] flex items-center justify-between transition-all duration-300`}>
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-gray-500/50 border-0" />
      <div className="flex items-center space-x-3 w-full">
        <div className="shrink-0">{config.icon}</div>
        <div className="flex-1 overflow-hidden">
          <p className="text-sm font-medium text-gray-100 truncate">{String(label)}</p>
          <p className={`text-xs mt-0.5 uppercase tracking-wider font-semibold ${config.text}`}>
            {String(status)}
          </p>
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-gray-500/50 border-0" />
    </div>
  );
};

const nodeTypes = {
  customTask: CustomTaskNode,
};

// ---------------------------------------------------------------------------
// Graph Component
// ---------------------------------------------------------------------------
interface WorkflowGraphProps {
  tasks: Array<{ node_id: string; status: string }>;
  dependencies: Array<{ id: string; depends_on: string[] }>;
}

export function WorkflowGraph({ tasks, dependencies }: WorkflowGraphProps) {
  // 1. Build a status map for quick lookup
  const statusMap = useMemo(() => {
    const m: Record<string, string> = {};
    tasks.forEach((t) => {
      m[t.node_id] = t.status;
    });
    return m;
  }, [tasks]);

  // 2. Compute Depths (Topology) for layout
  const depths = useMemo(() => {
    const d: Record<string, number> = {};
    const depsMap: Record<string, string[]> = {};
    
    dependencies.forEach(task => {
      depsMap[task.id] = task.depends_on || [];
    });

    const getDepth = (id: string, visited = new Set<string>()): number => {
      if (d[id] !== undefined) return d[id];
      if (visited.has(id)) return 0; // Cycle fallback
      
      const deps = depsMap[id] || [];
      if (deps.length === 0) {
        d[id] = 0;
        return 0;
      }

      visited.add(id);
      const maxDep = Math.max(...deps.map(dep => getDepth(dep, visited)));
      d[id] = maxDep + 1;
      return d[id];
    };

    dependencies.forEach(t => getDepth(t.id));
    return d;
  }, [dependencies]);

  // 3. Build Nodes & Edges
  const { nodes, edges } = useMemo(() => {
    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];

    // Group nodes by depth to calculate Y spacing
    const nodesByDepth: Record<number, string[]> = {};
    dependencies.forEach(t => {
      const depth = depths[t.id] || 0;
      if (!nodesByDepth[depth]) nodesByDepth[depth] = [];
      nodesByDepth[depth].push(t.id);
    });

    // Create Nodes
    Object.entries(nodesByDepth).forEach(([depthStr, ids]) => {
      const depth = parseInt(depthStr);
      const x = depth * 320; // 320px horizontal spacing
      
      ids.forEach((id, index) => {
        // Vertical centering: subtract half the height of all items at this depth
        const yOffset = (index - (ids.length - 1) / 2) * 120; 
        const y = 200 + yOffset; // Center at Y=200

        newNodes.push({
          id,
          type: "customTask",
          position: { x, y },
          data: {
            label: id,
            status: statusMap[id] || "PENDING",
          },
        });
      });
    });

    // Create Edges
    dependencies.forEach(task => {
      (task.depends_on || []).forEach(depId => {
        const sourceStatus = statusMap[depId] || "PENDING";
        const isAnimated = sourceStatus === "IN_PROGRESS" || sourceStatus === "PENDING";
        const strokeColor = sourceStatus === "COMPLETED" ? "#10b981" : "#4b5563"; // green or gray
        
        newEdges.push({
          id: `e-${depId}-${task.id}`,
          source: depId,
          target: task.id,
          animated: isAnimated,
          style: { stroke: strokeColor, strokeWidth: 2 },
        });
      });
    });

    return { nodes: newNodes, edges: newEdges };
  }, [dependencies, statusMap, depths]);

  return (
    <div className="w-full h-full min-h-[400px] bg-black/20 rounded-xl border border-card-border overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#333" gap={20} />
        <Controls className="bg-card border border-card-border !fill-gray-400" />
      </ReactFlow>
    </div>
  );
}
