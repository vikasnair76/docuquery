import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [documents, setDocuments] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");

  const [selectedDocument, setSelectedDocument] = useState(null);

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState("");

  const [deletingId, setDeletingId] = useState(null);

  const fetchDocuments = async () => {
    try {
      const response = await fetch(`${API_URL}/documents`);
      const data = await response.json();

      setDocuments(data.documents || []);
    } catch (error) {
      console.error("Failed to fetch documents:", error);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleUpload = async () => {
    if (!selectedFile) {
      setMessage("Please choose a PDF first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      setUploading(true);
      setMessage("");

      const response = await fetch(
        `${API_URL}/documents/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        setMessage(data.detail || "Upload failed.");
        return;
      }

      setMessage("Document uploaded successfully.");
      setSelectedFile(null);

      await fetchDocuments();
    } catch (error) {
      console.error("Upload error:", error);
      setMessage("Something went wrong while uploading.");
    } finally {
      setUploading(false);
    }
  };

  const handleAsk = async () => {
    if (!selectedDocument) {
      setAskError("Please select a document first.");
      return;
    }

    if (!question.trim()) {
      setAskError("Please enter a question.");
      return;
    }

    try {
      setAsking(true);
      setAskError("");
      setAnswer("");
      setSources([]);

      const response = await fetch(
        `${API_URL}/documents/${selectedDocument.id}/ask`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question: question.trim(),
            top_k: 3,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        setAskError(data.detail || "Failed to get an answer.");
        return;
      }

      setAnswer(data.answer || "");
      setSources(data.sources || []);
    } catch (error) {
      console.error("Question error:", error);
      setAskError(
        "Something went wrong while asking the question."
      );
    } finally {
      setAsking(false);
    }
  };

  const handleDelete = async (document, event) => {
    event.stopPropagation();

    const confirmed = window.confirm(
      `Delete "${document.filename}"?`
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingId(document.id);
      setMessage("");

      const response = await fetch(
        `${API_URL}/documents/${document.id}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        setMessage(
          data.detail || "Failed to delete document."
        );
        return;
      }

      if (selectedDocument?.id === document.id) {
        setSelectedDocument(null);
        setQuestion("");
        setAnswer("");
        setSources([]);
        setAskError("");
      }

      setMessage("Document deleted successfully.");

      await fetchDocuments();
    } catch (error) {
      console.error("Delete error:", error);
      setMessage(
        "Something went wrong while deleting the document."
      );
    } finally {
      setDeletingId(null);
    }
  };

  const handleSelectDocument = (document) => {
    setSelectedDocument(document);
    setQuestion("");
    setAnswer("");
    setSources([]);
    setAskError("");
  };

  return (
    <div className="app">
      <header>
        <h1>DocuQuery</h1>
        <p>AI-powered document question answering</p>
      </header>

      <section className="card">
        <h2>Upload Document</h2>

        <input
          type="file"
          accept="application/pdf"
          onChange={(event) => {
            setSelectedFile(
              event.target.files?.[0] || null
            );
            setMessage("");
          }}
        />

        {selectedFile && (
          <p className="selected-file">
            Selected: {selectedFile.name}
          </p>
        )}

        <button
          onClick={handleUpload}
          disabled={uploading}
        >
          {uploading
            ? "Processing..."
            : "Upload PDF"}
        </button>

        {message && (
          <p className="message">
            {message}
          </p>
        )}
      </section>

      <section className="card">
        <h2>Uploaded Documents</h2>

        {documents.length === 0 ? (
          <p>No documents uploaded.</p>
        ) : (
          <div className="documents">
            {documents.map((document) => (
              <div
                className={`document-item ${
                  selectedDocument?.id === document.id
                    ? "selected-document"
                    : ""
                }`}
                key={document.id}
                onClick={() =>
                  handleSelectDocument(document)
                }
              >
                <div className="document-main">
                  <span>📄</span>

                  <div>
                    <strong>
                      {document.filename}
                    </strong>

                    <p>
                      Document #{document.id}
                    </p>
                  </div>
                </div>

                <button
                  className="delete-button"
                  onClick={(event) =>
                    handleDelete(document, event)
                  }
                  disabled={
                    deletingId === document.id
                  }
                >
                  {deletingId === document.id
                    ? "Deleting..."
                    : "Delete"}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {selectedDocument && (
        <section className="card selected-card">
          <h2>Ask Your Document</h2>

          <div className="selected-document-info">
            <span className="document-icon">
              📄
            </span>

            <div>
              <strong>
                {selectedDocument.filename}
              </strong>

              <p>
                Document #{selectedDocument.id}
              </p>
            </div>
          </div>

          <div className="question-area">
            <textarea
              placeholder="Ask a question about this document..."
              value={question}
              onChange={(event) => {
                setQuestion(event.target.value);
                setAskError("");
              }}
              rows={4}
            />

            <button
              onClick={handleAsk}
              disabled={asking}
            >
              {asking
                ? "Thinking..."
                : "Ask Question"}
            </button>
          </div>

          {askError && (
            <p className="error-message">
              {askError}
            </p>
          )}

          {answer && (
            <div className="answer-section">
              <h3>Answer</h3>

              <div className="answer-text">
                <ReactMarkdown>
                  {answer}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {sources.length > 0 && (
            <div className="sources-section">
              <h3>Sources</h3>

              {sources.map((source) => (
                <details
                  className="source-item"
                  key={`${source.source}-${source.chunk_index}`}
                >
                  <summary>
                    <strong>
                      Source {source.source}
                    </strong>

                    <span>
                      Similarity:{" "}
                      {source.similarity}
                    </span>
                  </summary>

                  <p>
                    {source.content}
                  </p>
                </details>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default App;