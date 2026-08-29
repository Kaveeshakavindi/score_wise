import { FormEvent, useRef, useState } from "react";
import { ApiError, SyllabusDocument, uploadDocument } from "../api";

export function UploadForm({ onUploaded }: { onUploaded: (doc: SyllabusDocument) => void }) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [subject, setSubject] = useState("Information & Communication Technology");
  const [gradeLevel, setGradeLevel] = useState("13");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError("Choose a PDF file first.");
      return;
    }

    setError(null);
    setStatus(null);
    setSubmitting(true);
    try {
      const doc = await uploadDocument({ file, subject, gradeLevel });
      setStatus(`Uploaded "${doc.filename}" — ${doc.chunk_count} chunks indexed.`);
      onUploaded(doc);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="card upload-form" onSubmit={handleSubmit}>
      <h2>Upload syllabus PDF</h2>

      <label>
        File
        <input ref={fileInputRef} type="file" accept="application/pdf,.pdf" required />
      </label>

      <div className="field-row">
        <label>
          Subject
          <input value={subject} onChange={(e) => setSubject(e.target.value)} required />
        </label>
        <label>
          Grade level
          <input value={gradeLevel} onChange={(e) => setGradeLevel(e.target.value)} required />
        </label>
      </div>

      {error && <p className="error-text">{error}</p>}
      {status && <p className="success-text">{status}</p>}

      <button type="submit" disabled={submitting}>
        {submitting ? "Uploading…" : "Upload"}
      </button>
    </form>
  );
}
