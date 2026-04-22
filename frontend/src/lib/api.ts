import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// ---------------------------------------------------------------------------
// Types & Interfaces
// ---------------------------------------------------------------------------
export interface WorkflowTemplate {
  template_id: string;
  name: string;
  description: string;
  definition: any;
  created_at: string;
}

export interface ExecutionSummary {
  execution_id: string;
  template_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TaskExecution {
  task_id: string;
  execution_id: string;
  node_id: string;
  status: string;
  retry_count: number;
  input: any;
  output: any;
  logs: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ExecutionDetail {
  execution_id: string;
  template_id: string;
  status: string;
  global_context: any;
  created_at: string;
  updated_at: string;
  tasks: TaskExecution[];
}

export interface ApproveTaskPayload {
  comment?: string;
  data?: any;
}

// ---------------------------------------------------------------------------
// API Methods
// ---------------------------------------------------------------------------

export const ApiClient = {
  // Templates
  uploadTemplate: async (payload: { name: string; description: string; definition: any }) => {
    const res = await api.post<WorkflowTemplate>("/templates", payload);
    return res.data;
  },
  
  getTemplates: async () => {
    const res = await api.get<WorkflowTemplate[]>("/templates");
    return res.data;
  },

  getTemplate: async (id: string) => {
    const res = await api.get<WorkflowTemplate>(`/templates/${id}`);
    return res.data;
  },

  // Executions
  triggerExecution: async (template_id: string, global_context: any) => {
    const res = await api.post("/executions", { template_id, global_context });
    return res.data;
  },

  getExecutions: async () => {
    const res = await api.get<ExecutionSummary[]>("/executions");
    return res.data;
  },

  getExecution: async (id: string) => {
    const res = await api.get<ExecutionDetail>(`/executions/${id}`);
    return res.data;
  },

  // Controls
  pauseExecution: async (id: string) => {
    const res = await api.post(`/executions/${id}/pause`);
    return res.data;
  },

  resumeExecution: async (id: string) => {
    const res = await api.post(`/executions/${id}/resume`);
    return res.data;
  },

  terminateExecution: async (id: string) => {
    const res = await api.post(`/executions/${id}/terminate`);
    return res.data;
  },

  // Human in the Loop
  approveTask: async (taskId: string, payload: ApproveTaskPayload = {}) => {
    const res = await api.post(`/tasks/${taskId}/approve`, payload);
    return res.data;
  },
};
