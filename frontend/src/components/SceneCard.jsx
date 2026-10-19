import { useState } from "react";

export default function SceneCard({
  scene,
  engines,
  onSavePrompt,
  onGenerate,
  onRegenerate,
  onDelete,
}) {
  const [prompt, setPrompt] = useState(scene.image_prompt);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [feedback, setFeedback] = useState(scene.feedback || "");
  const availableEngines = (engines || []).filter((e) => e.available);
  const [engineId, setEngineId] = useState(
    scene.engine_id || availableEngines[0]?.id || ""
  );

  async function handleSave() {
    setSaving(true);
    try {
      await onSavePrompt(scene.id, prompt);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await onDelete(scene.id);
    } catch {
      setDeleting(false);
    }
  }

  function handleRegenerate() {
    if (!feedback.trim()) return;
    onRegenerate(scene.id, feedback.trim(), engineId);
  }

  const engineSelect = availableEngines.length > 0 && (
    <select value={engineId} onChange={(e) => setEngineId(e.target.value)}>
      {availableEngines.map((e) => (
        <option key={e.id} value={e.id}>
          {e.label}
        </option>
      ))}
    </select>
  );

  return (
    <div className="scene-card">
      <div className="scene-header">
        Scene {scene.index + 1}{" "}
        <span className={`status status-${scene.status}`}>{scene.status}</span>
        {scene.manual && <span className="status status-manual">manual</span>}
      </div>
      <p className="scene-summary">{scene.summary}</p>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={3}
      />
      <div className="scene-actions">
        <button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save prompt"}
        </button>
        {engineSelect}
        <button
          onClick={() => onGenerate(scene.id, engineId)}
          disabled={scene.status === "generating"}
        >
          {scene.status === "generating" ? "Generating..." : "Generate image"}
        </button>
        <button className="delete-btn" onClick={handleDelete} disabled={deleting}>
          {deleting ? "Deleting..." : "Delete"}
        </button>
      </div>
      {scene.status === "generating" && (
        <div className="scene-progress">
          {scene.progress ? (
            <>
              <progress value={scene.progress.value} max={scene.progress.max} />
              <span>
                step {scene.progress.value}/{scene.progress.max}
              </span>
            </>
          ) : (
            <span>queued…</span>
          )}
        </div>
      )}
      {scene.error && <p className="scene-error">{scene.error}</p>}
      {scene.image_path && (
        <>
          <img className="scene-image" src={scene.image_path} alt={scene.summary} />
          {scene.engine_id && (
            <p className="scene-engine-note">
              made with:{" "}
              {engines?.find((e) => e.id === scene.engine_id)?.label ??
                scene.engine_id}
            </p>
          )}
          <div className="scene-feedback">
            <textarea
              placeholder="What's wrong with this image? (e.g. hands look contorted)"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={2}
            />
            <div className="scene-feedback-actions">
              {engineSelect}
              <button
                onClick={handleRegenerate}
                disabled={scene.status === "generating" || !feedback.trim()}
              >
                {scene.status === "generating"
                  ? "Generating..."
                  : "Regenerate with fix"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
