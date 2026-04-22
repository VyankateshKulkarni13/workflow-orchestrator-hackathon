"use client";

import { useEffect, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { Upload, Play, FileJson, X, PlusCircle, ServerCog } from "lucide-react";
import { ApiClient, WorkflowTemplate } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function TemplatesPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplate | null>(null);
  const [triggerContext, setTriggerContext] = useState("{\n  \n}");
  const [isTriggering, setIsTriggering] = useState(false);

  const fetchTemplates = async () => {
    try {
      const data = await ApiClient.getTemplates();
      setTemplates(data);
    } catch (err) {
      setError("Failed to fetch templates.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const json = JSON.parse(text);
      
      const name = json.name || file.name.replace(".json", "");
      const desc = json._description || json.description || "Uploaded from dashboard";

      await ApiClient.uploadTemplate({
        name,
        description: desc,
        definition: json,
      });

      // Refresh list
      fetchTemplates();
    } catch (err: any) {
      alert("Failed to upload template: " + (err.message || "Invalid JSON"));
    }
    
    // Clear input
    e.target.value = "";
  };

  const openTriggerModal = (template: WorkflowTemplate) => {
    setSelectedTemplate(template);
    setIsModalOpen(true);
    // Provide a sensible default context for the demo
    setTriggerContext(JSON.stringify({
      "order_id": "ORD-DEMO-001",
      "customer_id": "CUST-999",
      "customer_email": "demo@example.com",
      "product_id": "ITEM-123",
      "quantity": 1,
      "total_amount": 99.99,
      "currency": "USD"
    }, null, 2));
  };

  const handleTrigger = async () => {
    if (!selectedTemplate) return;
    
    try {
      setIsTriggering(true);
      const parsedContext = JSON.parse(triggerContext);
      
      const res = await ApiClient.triggerExecution(selectedTemplate.template_id, parsedContext);
      
      // Navigate to the execution detail page
      if (res.details?.execution_id) {
        router.push(`/executions/${res.details.execution_id}`);
      }
    } catch (err: any) {
      alert("Failed to trigger execution: " + (err.response?.data?.detail || err.message));
    } finally {
      setIsTriggering(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-20">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Template Library</h1>
          <p className="text-gray-400 mt-1">Manage and trigger your DAG workflow definitions.</p>
        </div>
        
        {/* Upload Button */}
        <label className="cursor-pointer bg-card hover:bg-card-hover border border-card-border text-gray-200 px-4 py-2 rounded-lg font-medium transition-colors flex items-center shadow-lg">
          <Upload className="w-4 h-4 mr-2 text-blue-400" />
          Upload JSON
          <input 
            type="file" 
            accept=".json" 
            className="hidden" 
            onChange={handleFileUpload}
          />
        </label>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-lg">
          {error}
        </div>
      )}

      {/* Templates List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          <div className="col-span-full py-12 text-center text-gray-500">Loading...</div>
        ) : templates.length === 0 ? (
          <div className="col-span-full py-12 text-center text-gray-500 glass rounded-xl border border-card-border">
            <FileJson className="w-12 h-12 mx-auto mb-4 opacity-20" />
            <p>No templates found. Upload a workflow JSON to get started.</p>
          </div>
        ) : (
          templates.map((template) => (
            <div key={template.template_id} className="glass rounded-xl border border-card-border flex flex-col overflow-hidden group">
              <div className="p-5 flex-1">
                <div className="flex items-start justify-between">
                  <div className="p-2 bg-blue-500/10 rounded-lg">
                    <ServerCog className="w-5 h-5 text-blue-400" />
                  </div>
                  <span className="text-xs font-mono text-gray-500 bg-black/30 px-2 py-1 rounded">
                    {template.template_id.substring(0, 8)}
                  </span>
                </div>
                <h3 className="mt-4 font-semibold text-gray-100 text-lg leading-tight">{template.name}</h3>
                <p className="mt-2 text-sm text-gray-400 line-clamp-2">{template.description}</p>
                
                <div className="mt-4 pt-4 border-t border-card-border flex items-center justify-between text-xs text-gray-500">
                  <span>{template.definition?.tasks?.length || 0} nodes</span>
                  <span>{formatDistanceToNow(new Date(template.created_at), { addSuffix: true })}</span>
                </div>
              </div>
              
              <div className="bg-black/20 p-4 border-t border-card-border">
                <button 
                  onClick={() => openTriggerModal(template)}
                  className="w-full flex items-center justify-center space-x-2 bg-primary/10 hover:bg-primary/20 text-blue-400 border border-primary/20 hover:border-primary/40 py-2 rounded-lg transition-colors font-medium text-sm"
                >
                  <Play className="w-4 h-4" />
                  <span>Trigger Execution</span>
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Trigger Modal */}
      {isModalOpen && selectedTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass w-full max-w-2xl rounded-2xl border border-card-border shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between p-6 border-b border-card-border bg-black/20">
              <div>
                <h2 className="text-xl font-semibold text-gray-100">Trigger Execution</h2>
                <p className="text-sm text-gray-400 mt-1">Template: <span className="text-gray-200">{selectedTemplate.name}</span></p>
              </div>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto flex-1">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Global Context Payload (JSON)
              </label>
              <textarea
                value={triggerContext}
                onChange={(e) => setTriggerContext(e.target.value)}
                className="w-full h-64 bg-black/50 border border-card-border rounded-lg p-4 font-mono text-sm text-green-400 focus:outline-none focus:border-primary/50 transition-colors"
                spellCheck={false}
              />
              <p className="text-xs text-gray-500 mt-2">
                This payload will be available to all workers as `global_context`.
              </p>
            </div>
            
            <div className="p-6 border-t border-card-border bg-black/20 flex justify-end space-x-3">
              <button 
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 rounded-lg font-medium text-gray-300 hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={handleTrigger}
                disabled={isTriggering}
                className="bg-primary hover:bg-primary-hover text-white px-6 py-2 rounded-lg font-medium transition-colors flex items-center disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-500/20"
              >
                {isTriggering ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin mr-2"></div>
                    Starting...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    Launch Workflow
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
