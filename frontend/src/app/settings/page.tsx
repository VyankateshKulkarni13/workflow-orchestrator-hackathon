export default function SettingsPage() {
  return (
    <div className="max-w-4xl mx-auto py-12">
      <h1 className="text-2xl font-bold text-gray-100">Settings</h1>
      <p className="text-gray-400 mt-2">Preferences and configurations will appear here.</p>
      
      <div className="mt-8 glass rounded-xl border border-card-border p-6">
        <h2 className="text-lg font-semibold text-gray-200">System Info</h2>
        <div className="mt-4 space-y-2">
          <div className="flex justify-between border-b border-card-border py-2">
            <span className="text-gray-500">API Endpoint</span>
            <span className="font-mono text-sm text-blue-400">{process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}</span>
          </div>
          <div className="flex justify-between border-b border-card-border py-2">
            <span className="text-gray-500">Frontend Version</span>
            <span className="font-mono text-sm text-gray-300">v1.0.0</span>
          </div>
        </div>
      </div>
    </div>
  );
}
