import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import ResultPage from "./ResultPage";
import UploadPage from "./UploadPage";
import "./App.css";

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32" fill="none">
        <path
          d="M16 3.5 26 7v7.4c0 6.5-4 11.6-10 14.1-6-2.5-10-7.6-10-14.1V7l10-3.5Z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path
          d="m11.5 15.8 3 3 6-6.2"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <header className="site-header">
          <Link className="brand" to="/" aria-label="VeriDoc AI home">
            <BrandMark />
            <span>
              VeriDoc<span className="brand-ai"> AI</span>
            </span>
          </Link>
          <div className="header-status">
            <span className="status-dot" aria-hidden="true" />
            AI verification portal
          </div>
        </header>

        <main className="site-main">
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/verify/:verification_id" element={<ResultPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        <footer className="site-footer">
          <span>VeriDoc AI</span>
          <span>Certificate authentication portal</span>
        </footer>
      </div>
    </BrowserRouter>
  );
}
