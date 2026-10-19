import { useEffect, useState } from "react";
import { api } from "../api.js";

const FORMATS = [
  { id: "pdf", label: "PDF" },
  { id: "web", label: "Animated web page" },
  { id: "epub", label: "EPUB" },
  { id: "png", label: "PNG set" },
  { id: "mov", label: "Video (.mov)" },
];

export default function Publish({ novellaId }) {
  const [files, setFiles] = useState([]);
  const [busyFormat, setBusyFormat] = useState(null);
  const [error, setError] = useState(null);

  async function refresh() {
    const data = await api.listExports(novellaId);
    setFiles(data.files);
  }

  useEffect(() => {
    refresh().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [novellaId]);

  async function handleExport(format) {
    setBusyFormat(format);
    setError(null);
    try {
      await api.exportNovella(novellaId, format);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyFormat(null);
    }
  }

  return (
    <div className="characters-section">
      <h2>Publish</h2>
      <p className="settings-note">
        Writes the chosen format into this project's exports folder. Every
        format needs at least one scene with a generated image.
      </p>
      {error && <p className="error">{error}</p>}

      <div className="publish-formats">
        {FORMATS.map((f) => (
          <button
            key={f.id}
            onClick={() => handleExport(f.id)}
            disabled={busyFormat !== null}
          >
            {busyFormat === f.id ? "Publishing…" : f.label}
          </button>
        ))}
      </div>

      {files.length > 0 && (
        <div className="publish-files">
          <p className="settings-note">Exported files:</p>
          <ul className="url-results">
            {files.map((f) => (
              <li key={f.filename} className="url-ok">
                <a href={f.download_url} target="_blank" rel="noreferrer">
                  {f.filename}
                </a>{" "}
                <span className="url-error">
                  ({Math.round(f.size_bytes / 1024)} KB)
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
