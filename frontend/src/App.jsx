import { Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar.jsx";
import RequestsPage from "./pages/RequestsPage.jsx";
import RequestDetailPage from "./pages/RequestDetailPage.jsx";
import CostsPage from "./pages/CostsPage.jsx";

export default function App() {
  return (
    <div className="layout">
      <Sidebar />
      <main className="content">
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
