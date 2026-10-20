import { useState } from "react";
import { api } from "../api.js";

const SOURCE_TABS = [
  { id: "paste", label: "Paste text" },
  { id: "pdf", label: "Upload PDF" },
  { id: "urls", label: "From URLs" },
];

export default function UploadForm({
  onSubmit,
  busy,
  providers,
  defaultProviderId,
  ollamaModels,
}) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [targetSceneCount, setTargetSceneCount] = useState("");
  // Either a bare provider id ("anthropic"/"openai") or "ollama:<model name>"
  // - Ollama needs a specific model, not just the provider, picked right
  // here rather than requiring a trip to Settings.
  const [modelSelection, setModelSelection] = useState("");
  const [sourceTab, setSourceTab] = useState("paste");
  const [urlsInput, setUrlsInput] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState(null);
  const [urlResults, setUrlResults] = useState(null);

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setText(String(reader.result || ""));
    reader.readAsText(file);
    if (!title) setTitle(file.name.replace(/\.[^.]+$/, ""));
  }

  async function handlePdfChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setExtracting(true);
    setExtractError(null);
    try {
      const result = await api.extractPdf(file);
      setText(result.text);
      if (!title) setTitle(file.name.replace(/\.[^.]+$/, ""));
      setSourceTab("paste");
    } catch (err) {
      setExtractError(err.message);
    } finally {
      setExtracting(false);
    }
  }

  async function handleFetchUrls() {
    const urls = urlsInput
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
    if (urls.length === 0) return;
    setExtracting(true);
    setExtractError(null);
    setUrlResults(null);
    try {
      const result = await api.extractUrls(urls);
      setText(result.text);
      setUrlResults(result.results);
      setSourceTab("paste");
    } catch (err) {
      setExtractError(err.message);
    } finally {
      setExtracting(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!title.trim() || !text.trim()) return;
    const count = parseInt(targetSceneCount, 10);
    const [textProviderId, ollamaModel] = modelSelection.startsWith("ollama:")
      ? ["ollama", modelSelection.slice("ollama:".length)]
      : [modelSelection, null];
    onSubmit(
      title.trim(),
      text,
      Number.isFinite(count) && count > 0 ? count : null,
      textProviderId || null,
      ollamaModel
    );
  }

  return (
    <form onSubmit={handleSubmit} className="upload-form">
      <input
        type="text"
        placeholder="Novella title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />

      <div className="source-tabs">
        {SOURCE_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`source-tab ${sourceTab === tab.id ? "source-tab-active" : ""}`}
            onClick={() => {
              setSourceTab(tab.id);
              setExtractError(null);
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {extractError && <p className="error">{extractError}</p>}

      {urlResults && urlResults.some((r) => !r.ok) && (
        <ul className="url-results">
          {urlResults
            .filter((r) => !r.ok)
            .map((r) => (
              <li key={r.url} className="url-failed">
                ✕ {r.url}
                <span className="url-error"> — {r.error}</span>
              </li>
            ))}
        </ul>
      )}

      {sourceTab === "pdf" && (
        <input type="file" accept=".pdf" onChange={handlePdfChange} disabled={extracting} />
      )}

      {sourceTab === "urls" && (
        <div className="url-ingest">
          <textarea
            placeholder={"One URL per line\nhttps://example.com/chapter-one\nhttps://example.com/chapter-two"}
            value={urlsInput}
            onChange={(e) => setUrlsInput(e.target.value)}
            rows={4}
          />
          <button type="button" onClick={handleFetchUrls} disabled={extracting || !urlsInput.trim()}>
            {extracting ? "Fetching…" : "Fetch & use these pages"}
          </button>
          {urlResults && (
            <ul className="url-results">
              {urlResults.map((r) => (
                <li key={r.url} className={r.ok ? "url-ok" : "url-failed"}>
                  {r.ok ? "✓" : "✕"} {r.url}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {sourceTab === "paste" && (
        <input type="file" accept=".txt,.md" onChange={handleFileChange} />
      )}

      <textarea
        placeholder="...or paste your novella text here"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={10}
      />
      <label className="scene-count-field">
        Target number of scenes (optional)
        <input
          type="number"
          min="1"
          placeholder="let the AI decide"
          value={targetSceneCount}
          onChange={(e) => setTargetSceneCount(e.target.value)}
        />
      </label>
      {providers && providers.length > 0 && (
        <label className="scene-count-field">
          Scene-breakdown model
          <select
            value={modelSelection}
            onChange={(e) => setModelSelection(e.target.value)}
          >
            <option value="">
              Default ({providers.find((p) => p.id === defaultProviderId)?.label || defaultProviderId})
            </option>
            {providers
              .filter((p) => p.available)
              .map((p) =>
                p.id === "ollama" && ollamaModels?.length > 0 ? (
                  ollamaModels.map((m) => (
                    <option key={`ollama:${m.name}`} value={`ollama:${m.name}`}>
                      Ollama — {m.name}
                      {m.size_bytes ? ` (${(m.size_bytes / 1e9).toFixed(1)} GB)` : ""}
                    </option>
                  ))
                ) : (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                )
              )}
          </select>
        </label>
      )}
      <button type="submit" disabled={busy || extracting}>
        {busy ? "Working..." : "Create & break into scenes"}
      </button>
    </form>
  );
}
