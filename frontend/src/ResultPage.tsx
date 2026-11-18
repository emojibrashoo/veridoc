import { Link, useLocation, useParams } from "react-router-dom";
import { apiBaseUrl, type VerificationResponse } from "./api";

interface VerificationLocationState {
  verification?: VerificationResponse;
}

const resultLabels = {
  authentic: "Authentic",
  suspicious: "Suspicious",
  fraudulent: "Fraudulent",
} satisfies Record<VerificationResponse["result"], string>;

export default function ResultPage() {
  const { verification_id: routeId } = useParams();
  const location = useLocation();
  const state = location.state as VerificationLocationState | null;
  const verification = state?.verification;

  if (
    !verification ||
    String(verification.verification_id) !== routeId
  ) {
    return (
      <section className="result-card unavailable-card">
        <span className="result-symbol result-symbol-neutral" aria-hidden="true">
          ?
        </span>
        <p className="eyebrow">RESULT NOT AVAILABLE</p>
        <h1>Open a result from your upload</h1>
        <p className="result-description">
          This result is not available in the current page session. Upload the
          certificate again to view its verification details.
        </p>
        <Link className="primary-button button-link" to="/">
          Upload certificate <span aria-hidden="true">→</span>
        </Link>
      </section>
    );
  }

  const resultClass = `result-${verification.result}`;
  const confidence = Math.round(verification.confidence_score * 100);
  const qrUrl = `${apiBaseUrl}/api/qr/${verification.verification_id}`;

  return (
    <section className="result-page">
      <div className="result-card">
        <div className="result-header">
          <div>
            <p className="eyebrow">VERIFICATION COMPLETE</p>
            <h1>Certificate result</h1>
          </div>
          <span className={`result-badge ${resultClass}`}>
            <span className={`badge-dot ${resultClass}`} aria-hidden="true" />
            {resultLabels[verification.result]}
          </span>
        </div>

        <div className="result-grid">
          <section className="result-panel confidence-panel">
            <p className="panel-label">AI CONFIDENCE</p>
            <div className="confidence-value">
              {confidence}
              <span>%</span>
            </div>
            <div
              className="confidence-track"
              role="progressbar"
              aria-label="Confidence score"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={confidence}
            >
              <span
                className={`confidence-fill ${resultClass}`}
                style={{ width: `${confidence}%` }}
              />
            </div>
            <p className="muted-copy">
              Confidence score: {verification.confidence_score.toFixed(2)}
            </p>
          </section>

          <section className="result-panel id-panel">
            <p className="panel-label">VERIFICATION ID</p>
            <p className="verification-id">#{verification.verification_id}</p>
            <p className="muted-copy">Keep this ID for your records.</p>
          </section>
        </div>

        <section className="text-panel">
          <div className="section-title-row">
            <div>
              <p className="panel-label">DOCUMENT ANALYSIS</p>
              <h2>Extracted text</h2>
            </div>
            <span className="text-tag">OCR</span>
          </div>
          <pre className="extracted-text">
            {verification.extracted_text.trim() ||
              "No readable text was detected in this image."}
          </pre>
        </section>

        {verification.result === "authentic" && verification.qr_code_data && (
          <section className="qr-panel">
            <div>
              <p className="panel-label">SHAREABLE PROOF</p>
              <h2>Verification QR code</h2>
              <p className="muted-copy">
                Scan to open the verification reference.
              </p>
              <a
                className="verification-link"
                href={verification.qr_code_data}
                target="_blank"
                rel="noreferrer"
              >
                {verification.qr_code_data}
              </a>
            </div>
            <img
              className="qr-image"
              src={qrUrl}
              alt={`QR code for verification ${verification.verification_id}`}
            />
          </section>
        )}

        <div className="result-footer">
          <p>
            Blockchain record: <code>{verification.blockchain_hash}</code>
          </p>
          <Link className="secondary-button" to="/">
            Verify another
          </Link>
        </div>
      </div>
    </section>
  );
}
