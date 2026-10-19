import { useState } from "react";

export default function UploadForm({ onSubmit, busy, providers, defaultProviderId }) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [targetSceneCount, setTargetSceneCount] = useState("");
  const [textProviderId, setTextProviderId] = useState("");

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setText(String(reader.result || ""));
    reader.readAsText(file);
    if (!title) setTitle(file.name.replace(/\.[^.]+$/, ""));
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!title.trim() || !text.trim()) return;
    const count = parseInt(targetSceneCount, 10);
    onSubmit(
      title.trim(),
      text,
      Number.isFinite(count) && count > 0 ? count : null,
      textProviderId || null
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
      <input type="file" accept=".txt,.md" onChange={handleFileChange} />
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
            value={textProviderId}
            onChange={(e) => setTextProviderId(e.target.value)}
          >
            <option value="">
              Default ({providers.find((p) => p.id === defaultProviderId)?.label || defaultProviderId})
            </option>
            {providers
              .filter((p) => p.available)
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
          </select>
        </label>
      )}
      <button type="submit" disabled={busy}>
        {busy ? "Working..." : "Create & break into scenes"}
      </button>
    </form>
  );
}
