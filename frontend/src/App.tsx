import { Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import RequestsPage from "./pages/RequestsPage";
import RequestDetailPage from "./pages/RequestDetailPage";
import CostsPage from "./pages/CostsPage";

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="min-w-0 flex-1 max-w-6xl px-8 py-7">
        <Routes>
          <Route path="/" element={<Navigate to="/requests" replace />} />
          <Route path="/requests" element={<RequestsPage />} />
          <Route path="/requests/:id" element={<RequestDetailPage />} />
          <Route path="/costs" element={<CostsPage />} />
        </Routes>
      </main>
    </div>
  );
}
