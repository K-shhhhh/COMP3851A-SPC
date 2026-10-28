import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import LoginPage from "./pages/Login/LoginPage.jsx";
import RegisterPage from "./pages/Register/RegisterPage";
import DashboardPage from "./pages/Dashboard/DashboardPage";
import UploadNotesPage from "./pages/UploadNotes/UploadNotesPage";
import NotesPage from "./pages/Notes/NotesPage.jsx";
import CompanionPage from "./pages/Companion/CompanionPage";
import GroupStudyPage from "./pages/GroupStudy/GroupStudyPage";
import KnowledgeGraphPage from "./pages/KnowledgeGraph/KnowledgeGraphPage.jsx";
import ProfilePage from "./pages/Profile/ProfilePage.jsx";
import SettingsPage from "./pages/Settings/SettingsPage.jsx";
import MyReportsPage from "./pages/Reports/MyReportsPage.jsx";
import PdfViewerPage from "./pages/PdfViewer/PdfViewerPage.jsx";

import ProtectedRoute from "./routes/ProtectedRoute.jsx";
import RoleRedirect from "./routes/RoleRedirect.jsx";
import GuestRoute from "./routes/GuestRoute.jsx";
import AdminLayout from "./pages/Admin/AdminLayout.jsx";
import AdminDashboardPage from "./pages/Admin/AdminDashboardPage.jsx";
import AdminCollectionPage from "./pages/Admin/AdminCollectionPage.jsx";
import AdminStudyGroupsPage from "./pages/Admin/AdminStudyGroupsPage.jsx";
import AdminAttachmentsPage from "./pages/Admin/AdminAttachmentsPage.jsx";
import AdminReportsPage from "./pages/Admin/AdminReportsPage.jsx";

import "./styles/styles.css";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <RoleRedirect />
          }
        />

        <Route
          path="/login"
          element={<GuestRoute><LoginPage /></GuestRoute>}
        />

        <Route
          path="/register"
          element={<GuestRoute><RegisterPage /></GuestRoute>}
        />

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

        {/*
         * My Notes Library.
         *
         * This page is protected because every Notes API request
         * depends on the authenticated student's bearer token.
         */}
        <Route
          path="/notes"
          element={
            <ProtectedRoute>
              <NotesPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/notes/:noteId/view"
          element={
            <ProtectedRoute>
              <PdfViewerPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/groups"
          element={
            <ProtectedRoute>
             <GroupStudyPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/knowledge-graph"
          element={
            <ProtectedRoute>
              <KnowledgeGraphPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/reports"
          element={
            <ProtectedRoute>
              <MyReportsPage />
            </ProtectedRoute>
          }
        />

        {/* Admin pages share the login but have their own role-protected shell. */}
        <Route
          path="/admin"
          element={<ProtectedRoute requiredRole="admin"><AdminLayout /></ProtectedRoute>}
        >
          <Route index element={<AdminDashboardPage />} />
          <Route path="users" element={<AdminCollectionPage section="users" />} />
          <Route path="study-groups" element={<AdminStudyGroupsPage />} />
          <Route path="attachments" element={<AdminAttachmentsPage />} />
          <Route path="reports" element={<AdminReportsPage />} />
          <Route path="system-logs" element={<AdminCollectionPage section="system-logs" />} />
        </Route>

        <Route
          path="*"
          element={
            <Navigate
              to="/"
              replace
            />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;