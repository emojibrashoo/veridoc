import axios from "axios";

export type VerificationResult = "authentic" | "suspicious" | "fraudulent";

export interface VerificationResponse {
  verification_id: number;
  result: VerificationResult;
  confidence_score: number;
  extracted_text: string;
  blockchain_hash: string;
  qr_code_data: string | null;
}

export const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export async function uploadCertificate(
  file: File,
): Promise<VerificationResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await axios.post<VerificationResponse>(
    `${apiBaseUrl}/api/verify`,
    formData,
  );
  return response.data;
}

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String(item.msg)
            : "Request validation failed",
        )
        .join(", ");
    }
    if (error.response?.status === 503) {
      return "A required service is unavailable. Check that the API, databases, and Tesseract OCR are running.";
    }
    return error.message || "The request could not be completed.";
  }
  return "An unexpected error occurred. Please try again.";
}
