import { BookOpen, Bot, FileText, HelpCircle, MessageCircle, ShieldCheck, Users } from "lucide-react";
import { Link } from "react-router-dom";
import AppShell from "../../components/layout/AppShell.jsx";
import "./help.css";

const aiModes = [
  { name: "Companion", description: "Ask the AI a question about your study material or the group discussion.", example: "@Companion explain this topic simply" },
  { name: "Summarizer", description: "Request a concise summary of study content.", example: "@Summarizer give us the key points" },
  { name: "QuizMaster", description: "Practise with study questions and check what you understand.", example: "@QuizMaster quiz us on this chapter" },
  { name: "Facilitator", description: "Help guide a group discussion or break down a difficult concept.", example: "@Facilitator help us discuss this problem" },
];

export default function HelpPage() {
  return (
    <AppShell>
      <div className="spc-help-page">
        <header className="spc-help-header"><HelpCircle size={28} /><div><h1>Help & Guide</h1><p>New to Smart Peer Companion? Start here.</p></div></header>
        <section className="spc-help-section">
          <h2><BookOpen size={20} /> Getting started</h2>
          <ol>
            <li><Link to="/notes/upload">Upload a PDF</Link> of your learning materials.</li>
            <li>Open <Link to="/notes">My Notes</Link> to see your uploaded files.</li>
            <li>Visit the <Link to="/companion">AI Assistant</Link> to ask study questions and review the cited sources.</li>
            <li>Join or create a <Link to="/groups">Study Group</Link> to collaborate with classmates.</li>
          </ol>
        </section>
        <section className="spc-help-section">
          <h2><Bot size={20} /> AI modes in Study Groups</h2>
          <p>In a Study Group channel, type <strong>@</strong> in the message box to choose an AI mode or mention a member. Use the mode that best fits your goal.</p>
          <div className="spc-help-cards">
            {aiModes.map((mode) => <article className="spc-help-card" key={mode.name}><h3>{mode.name}</h3><p>{mode.description}</p><code>{mode.example}</code></article>)}
          </div>
        </section>
        <section className="spc-help-section"><h2><Users size={20} /> Study Groups and channels</h2><p>A <strong>Study Group</strong> is a space for classmates. A <strong>channel</strong> is a conversation within that group. Public groups can be discovered; private groups require an invitation. Members can share messages and, when allowed, PDF attachments.</p></section>
        <section className="spc-help-section"><h2><FileText size={20} /> Notes, sources, and citations</h2><p>When an AI answer includes a source citation, select it to open the referenced PDF in the viewer at the cited page. Always check the source, especially for important facts. If a PDF is still being processed, it may not be ready for AI questions yet.</p></section>
        <section className="spc-help-section"><h2><MessageCircle size={20} /> Mentions and notifications</h2><p>In a group message, type <strong>@</strong> and choose a member to mention them. Use the bell at the top of the app to read new group-message and mention notifications. Select a notification to open its group and channel. Manage notification preferences in <Link to="/settings">Settings</Link>.</p></section>
        <section className="spc-help-section"><h2><ShieldCheck size={20} /> Reporting inappropriate content</h2><p>Use a Report action when you encounter inappropriate messages or files. You can review your submissions in <Link to="/reports">My Reports</Link>.</p></section>
      </div>
    </AppShell>
  );
}
