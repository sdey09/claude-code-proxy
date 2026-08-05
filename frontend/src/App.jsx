import { Navigate, Route, Routes } from "react-router-dom";
import Nav from "./components/Nav.jsx";
import RequestsPage from "./pages/RequestsPage.jsx";
import RequestDetailPage from "./pages/RequestDetailPage.jsx";
import CostsPage from "./pages/CostsPage.jsx";

export default function App() {
  return (
    <>
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/requests" replace />} />
          <Route path="/requests" element={<RequestsPage />} />
          <Route path="/requests/:id" element={<RequestDetailPage />} />
          <Route path="/costs" element={<CostsPage />} />
        </Routes>
      </main>
    </>
  );
}
