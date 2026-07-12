import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import DashboardPage from "./pages/DashboardPage";
import GrammarPage from "./pages/GrammarPage";
import KnowledgeMapPage from "./pages/KnowledgeMapPage";
import QuizPage from "./pages/QuizPage";
import UploadPage from "./pages/UploadPage";
import VocabPage from "./pages/VocabPage";
import VocabReviewPage from "./pages/VocabReviewPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/vocab" element={<VocabPage />} />
        <Route path="/vocab/review" element={<VocabReviewPage />} />
        <Route path="/grammar" element={<GrammarPage />} />
        <Route path="/map" element={<KnowledgeMapPage />} />
        <Route path="/quiz" element={<QuizPage />} />
        <Route path="/upload" element={<UploadPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
