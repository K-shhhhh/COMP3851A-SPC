import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import LoginPage from "./pages/Login/LoginPage.jsx";
import RegisterPage from "./pages/Register/RegisterPage";
import DashboardPage from "./pages/Dashboard/DashboardPage";
import UploadNotesPage from "./pages/UploadNotes/UploadNotesPage";
import CompanionPage from "./pages/Companion/CompanionPage";

import ProtectedRoute from "./routes/ProtectedRoute.jsx";

import "./styles/styles.css";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />

        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/companion"
          element={
            <ProtectedRoute>
              <CompanionPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/notes/upload"
          element={
            <ProtectedRoute>
              <UploadNotesPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="*"
          element={<Navigate to="/dashboard" replace />}
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;