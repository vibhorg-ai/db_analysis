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
import { wsClient } from "./api/websocket.ts";

export default function App() {
  useEffect(() => {
    wsClient.connect();
    return () => wsClient.disconnect();
  }, []);

  return (
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
          <Route path="connections" element={<ConnectionsPage />} />
        </Route>
      </Routes>
    </AppProvider>
  );
}
