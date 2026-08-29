import { useEffect, useState } from "react";
import { ApiError, SessionExpiredError, SyllabusDocument, deleteDocument, listDocuments } from "../api";
import { UploadForm } from "./UploadForm";

export function DocumentsView({ onSessionExpired }: { onSessionExpired: () => void }) {
  const [documents, setDocuments] = useState<SyllabusDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      setDocuments(await listDocuments());
    } catch (err) {
      handleError(err);
    }
  }

  function handleError(err: unknown) {
    if (err instanceof SessionExpiredError) {
      onSessionExpired();
      return;
    }
    setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleDelete(id: string) {
    setDeletingId(id);
    setError(null);
    try {
      await deleteDocument(id);
      setPendingDeleteId(null);
      await refresh();
    } catch (err) {
      handleError(err);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="page">
      <UploadForm onUploaded={() => refresh()} />

      <div className="card">
        <h2>Syllabus documents</h2>
        {error && <p className="error-text">{error}</p>}

        {documents === null ? (
          <p className="subtle">Loading…</p>
        ) : documents.length === 0 ? (
          <p className="subtle">No syllabus documents uploaded yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Filename</th>
                <th>Subject</th>
                <th>Grade level</th>
                <th>Chunks</th>
                <th>Uploaded</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.filename}</td>
                  <td>{doc.subject}</td>
                  <td>{doc.topic ?? "—"}</td>
                  <td className="numeric">{doc.chunk_count}</td>
                  <td>{new Date(doc.uploaded_at).toLocaleString()}</td>
                  <td className="actions-cell">
                    {pendingDeleteId === doc.id ? (
                      <span className="confirm-delete">
                        <button
                          type="button"
                          className="danger"
                          disabled={deletingId === doc.id}
                          onClick={() => handleDelete(doc.id)}
                        >
                          {deletingId === doc.id ? "Deleting…" : "Confirm delete?"}
                        </button>
                        <button type="button" className="link" onClick={() => setPendingDeleteId(null)}>
                          Cancel
                        </button>
                      </span>
                    ) : (
                      <button type="button" className="link" onClick={() => setPendingDeleteId(doc.id)}>
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
