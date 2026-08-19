import { Navigate, Route, Routes } from "react-router-dom";
import AppShellWithAuth from "./components/AppShell";
import Landing from "./pages/Landing";
import AuthPage from "./pages/AuthPage";
import VerifyEmail from "./pages/VerifyEmail";
import Dashboard from "./pages/app/Dashboard";
import Inbox from "./pages/app/Inbox";
import Conversations from "./pages/app/Conversations";
import ConversationDetail from "./pages/app/ConversationDetail";
import Pages from "./pages/app/Pages";
import Jobs from "./pages/app/Jobs";
import Settings from "./pages/app/Settings";
import Memory from "./pages/app/Memory";
import Knowledge from "./pages/app/Knowledge";
import Training from "./pages/app/Training";
import Evaluation from "./pages/app/Evaluation";
import Analytics from "./pages/app/Analytics";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/verify-email" element={<VerifyEmail />} />

      <Route path="/app" element={<AppShellWithAuth />}>
        <Route index element={<Navigate to="/app/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="inbox" element={<Inbox />} />
        <Route path="conversations" element={<Conversations />} />
        <Route path="conversations/:id" element={<ConversationDetail />} />
        <Route path="pages" element={<Pages />} />
        <Route path="jobs" element={<Jobs />} />
        <Route path="settings" element={<Settings />} />
        <Route path="memory" element={<Memory />} />
        <Route path="knowledge" element={<Knowledge />} />
        <Route path="training" element={<Training />} />
        <Route path="evaluation" element={<Evaluation />} />
        <Route path="analytics" element={<Analytics />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
