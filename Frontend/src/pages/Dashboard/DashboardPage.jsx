import {
  BookOpen,
  Bot,
  BrainCircuit,
  Clock3,
  FileText,
  Upload,
  Users,
} from "lucide-react";

import { Link } from "react-router-dom";
import AppShell from "../../components/layout/AppShell.jsx";
import "./dashboard.css";

function DashboardPage() {
  return (
    <AppShell>
      <div className="dashboard-page">
        <section className="dashboard-header">
          <div>
            <p className="dashboard-eyebrow">Smart Peer Companion</p>
            <h1>Dashboard</h1>
            <p className="dashboard-subtitle">
              Manage your notes, learning tools, study groups and AI resources
              from one place.
            </p>
          </div>

          <Link to="/notes/upload" className="dashboard-upload-button">
            <Upload size={18} />
            Upload Notes
          </Link>
        </section>

        <section className="dashboard-stats">
          <div className="dashboard-stat-card">
            <div className="dashboard-stat-icon">
              <FileText size={22} />
            </div>

            <div>
              <span>Total Notes</span>
              <strong>24</strong>
              <small>Across all courses</small>
            </div>
          </div>

          <div className="dashboard-stat-card">
            <div className="dashboard-stat-icon">
              <BookOpen size={22} />
            </div>

            <div>
              <span>Active Courses</span>
              <strong>4</strong>
              <small>This semester</small>
            </div>
          </div>

          <div className="dashboard-stat-card">
            <div className="dashboard-stat-icon">
              <Users size={22} />
            </div>

            <div>
              <span>Study Groups</span>
              <strong>3</strong>
              <small>Currently joined</small>
            </div>
          </div>

          <div className="dashboard-stat-card">
            <div className="dashboard-stat-icon">
              <Clock3 size={22} />
            </div>

            <div>
              <span>Study Time</span>
              <strong>8.5h</strong>
              <small>This week</small>
            </div>
          </div>
        </section>

        <section className="dashboard-grid">
          <div className="dashboard-panel dashboard-recent">
            <div className="dashboard-panel-header">
              <div>
                <h2>Recent Notes</h2>
                <p>Your latest uploaded learning materials</p>
              </div>

              <Link to="/notes">View all</Link>
            </div>

            <div className="dashboard-note-list">
              <div className="dashboard-note-item">
                <div className="dashboard-note-icon">
                  <FileText size={20} />
                </div>

                <div className="dashboard-note-info">
                  <strong>Week 4 - Data Structures</strong>
                  <span>COMP2000</span>
                </div>

                <span className="dashboard-note-time">2 hours ago</span>
              </div>

              <div className="dashboard-note-item">
                <div className="dashboard-note-icon">
                  <FileText size={20} />
                </div>

                <div className="dashboard-note-info">
                  <strong>Lecture 6 - Database Design</strong>
                  <span>INFT3000</span>
                </div>

                <span className="dashboard-note-time">Yesterday</span>
              </div>

              <div className="dashboard-note-item">
                <div className="dashboard-note-icon">
                  <FileText size={20} />
                </div>

                <div className="dashboard-note-info">
                  <strong>Systems Analysis Notes</strong>
                  <span>SENG2130</span>
                </div>

                <span className="dashboard-note-time">2 days ago</span>
              </div>
            </div>
          </div>

          <div className="dashboard-panel">
            <div className="dashboard-panel-header">
              <div>
                <h2>Quick Actions</h2>
                <p>Continue your learning</p>
              </div>
            </div>

            <div className="dashboard-actions">
              <Link to="/notes/upload" className="dashboard-action-card">
                <div>
                  <Upload size={20} />
                </div>
                <span>
                  <strong>Upload Notes</strong>
                  <small>Add PDF, DOCX or images</small>
                </span>
              </Link>

              <Link to="/companion" className="dashboard-action-card">
                <div>
                  <Bot size={20} />
                </div>
                <span>
                  <strong>Ask AI Assistant</strong>
                  <small>Get help with your studies</small>
                </span>
              </Link>

              <Link to="/knowledge-graph" className="dashboard-action-card">
                <div>
                  <BrainCircuit size={20} />
                </div>
                <span>
                  <strong>Knowledge Graph</strong>
                  <small>Explore connected concepts</small>
                </span>
              </Link>

              <Link to="/groups" className="dashboard-action-card">
                <div>
                  <Users size={20} />
                </div>
                <span>
                  <strong>Study Groups</strong>
                  <small>Collaborate with classmates</small>
                </span>
              </Link>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

export default DashboardPage;