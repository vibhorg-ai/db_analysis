import { Component, type ReactNode } from "react";
import { Routes, Route } from "react-router-dom";
import { useEffect } from "react";
import { AppProvider } from "./context/AppContext.tsx";
import Layout from "./components/Layout.tsx";
import DashboardPage from "./pages/DashboardPage.tsx";
import QueryPage from "./pages/QueryPage.tsx";
import HealthPage from "./pages/HealthPage.tsx";
import IssuesPage from "./pages/IssuesPage.tsx";
import SandboxPage from "./pages/SandboxPage.tsx";
import ChatPage from "./pages/ChatPage.tsx";
import GraphPage from "./pages/GraphPage.tsx";
import ConnectionsPage from "./pages/ConnectionsPage.tsx";
import InsightsPage from "./pages/InsightsPage.tsx";
import SimulationPage from "./pages/SimulationPage.tsx";
import { wsClient } from "./api/websocket.ts";

class AppErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("App error:", error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-surface-950 text-white flex flex-col items-center justify-center p-8">
          <h1 className="text-xl font-bold text-red-400 mb-2">Something went wrong</h1>
          <p className="text-surface-400 text-sm mb-4">The app hit an error. Check the console or try refreshing.</p>
          <button
            type="button"
            className="btn-primary"
            onClick={() => this.setState({ hasError: false })}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  useEffect(() => {
    wsClient.connect();
    return () => wsClient.disconnect();
  }, []);

  return (
    <AppErrorBoundary>
      <AppProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="query" element={<QueryPage />} />
            <Route path="health" element={<HealthPage />} />
            <Route path="issues" element={<IssuesPage />} />
            <Route path="sandbox" element={<SandboxPage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="graph" element={<GraphPage />} />
            <Route path="insights" element={<InsightsPage />} />
            <Route path="simulation" element={<SimulationPage />} />
            <Route path="connections" element={<ConnectionsPage />} />
          </Route>
        </Routes>
      </AppProvider>
    </AppErrorBoundary>
  );
}
