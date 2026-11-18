import { useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { getApiErrorMessage, uploadCertificate } from "./api";

const MAX_FILE_SIZE = 5 * 1024 * 1024;

function isSupportedImage(file: File): boolean {
  const extensionIsSupported = /\.(jpe?g|png)$/i.test(file.name);
  const typeIsSupported = ["image/jpeg", "image/png"].includes(file.type);
  return extensionIsSupported && (!file.type || typeIsSupported);
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0] ?? null;
    setError(null);
    setFile(null);

    if (!selectedFile) {
      return;
    }
    if (!isSupportedImage(selectedFile)) {
      setError("Choose a JPG or PNG image.");
      event.target.value = "";
      return;
    }
    if (selectedFile.size === 0) {
      setError("The selected file is empty.");
      event.target.value = "";
      return;
    }
    if (selectedFile.size > MAX_FILE_SIZE) {
      setError("The image must be 5 MB or smaller.");
      event.target.value = "";
      return;
    }

    setFile(selectedFile);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || isSubmitting) {
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      const verification = await uploadCertificate(file);
      navigate(`/verify/${verification.verification_id}`, {
        state: { verification },
      });
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="upload-layout">
      <div className="intro">
        <p className="eyebrow">CERTIFICATE VERIFICATION</p>
        <h1>Know what’s real.</h1>
        <p className="intro-copy">
          Upload a certificate image and let VeriDoc AI inspect its text and
          visual signals.
        </p>
        <div className="trust-note">
          <span className="trust-icon" aria-hidden="true">
            ✓
          </span>
          <span>Secure analysis · Results in seconds</span>
        </div>
      </div>

      <form className="upload-card" onSubmit={handleSubmit}>
        <div className="card-heading">
          <div>
            <p className="eyebrow">START A CHECK</p>
            <h2>Upload certificate</h2>
          </div>
          <span className="step-pill">01 / 01</span>
        </div>

        <label className="drop-zone" htmlFor="certificate-file">
          <span className="upload-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path
                d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M5 14.5v3A2.5 2.5 0 0 0 7.5 20h9a2.5 2.5 0 0 0 2.5-2.5v-3"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span className="drop-title">
            {file ? file.name : "Choose a JPG or PNG image"}
          </span>
          <span className="drop-description">
            {file
              ? `${(file.size / 1024 / 1024).toFixed(2)} MB · Ready to verify`
              : "JPG or PNG · Maximum 5 MB"}
          </span>
          <span className="browse-button">Browse files</span>
          <input
            id="certificate-file"
            name="file"
            type="file"
            accept=".jpg,.jpeg,.png,image/jpeg,image/png"
            onChange={handleFileChange}
            disabled={isSubmitting}
          />
        </label>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <button
          className="primary-button"
          type="submit"
          disabled={!file || isSubmitting}
        >
          {isSubmitting ? (
            <>
              <span className="spinner" aria-hidden="true" />
              Analyzing certificate…
            </>
          ) : (
            <>
              Verify certificate
              <span aria-hidden="true">→</span>
            </>
          )}
        </button>
        <p className="privacy-note">
          Your image is processed securely for verification.
        </p>
      </form>

      <div className="process-row" aria-label="Verification steps">
        <span>
          <b>01</b> Upload image
        </span>
        <i aria-hidden="true" />
        <span>
          <b>02</b> AI analysis
        </span>
        <i aria-hidden="true" />
        <span>
          <b>03</b> View result
        </span>
      </div>
    </section>
  );
}
