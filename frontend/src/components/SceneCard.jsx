import { useState } from "react";
import { api, resolveAssetUrl } from "../api.js";
import Panel, { SCENE_TYPE_TO_ROOM } from "./Panel.jsx";

const GHOST_LABEL = {
  pending: "PENDING",
  generating: "DRAWING…",
  error: "FAILED",
};

export default function SceneCard({
  novellaId,
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
    scene.engine_id || scene.recommended_engine_id || availableEngines[0]?.id || ""
  );
  const [recommendation, setRecommendation] = useState(null);
  const [recommending, setRecommending] = useState(false);

  const recommendedEngine = engines?.find((e) => e.id === scene.recommended_engine_id);
  const room = SCENE_TYPE_TO_ROOM[scene.scene_type] || "spires";

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

  async function handleGetRecommendation() {
    setRecommending(true);
    try {
      const result = await api.recommendForScene(
        novellaId,
        scene.id,
        feedback.trim()
      );
      setRecommendation(result);
      if (result.recommended_engine_id) {
        setEngineId(result.recommended_engine_id);
      }
    } catch {
      // non-critical - leave the manual engine picker as the fallback
    } finally {
      setRecommending(false);
    }
  }

  const engineSelect = availableEngines.length > 0 && (
    <select value={engineId} onChange={(e) => setEngineId(e.target.value)}>
      {availableEngines.map((e) => (
        <option key={e.id} value={e.id}>
          {e.label}
          {e.id === scene.recommended_engine_id ? " (recommended)" : ""}
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
        {scene.scene_type && (
          <span className="scene-tag" title="heuristic scene-type classification">
            {scene.scene_type.replace("_", " ")}
          </span>
        )}
        {scene.complexity && (
          <span className="scene-tag" title="heuristic complexity classification">
            {scene.complexity}
          </span>
        )}
      </div>

      <Panel
        scene={room}
        image={resolveAssetUrl(scene.image_path)}
        alt={scene.summary}
        caption={scene.image_path ? scene.summary : undefined}
        ghostLabel={!scene.image_path ? GHOST_LABEL[scene.status] || "PENDING" : undefined}
      />

      <p className="scene-summary">{scene.summary}</p>
      {recommendedEngine && (
        <p className="scene-recommendation">
          Recommended engine: <strong>{recommendedEngine.label}</strong>
        </p>
      )}
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
              onChange={(e) => {
                setFeedback(e.target.value);
                setRecommendation(null);
              }}
              rows={2}
            />
            <div className="scene-feedback-actions">
              {engineSelect}
              <button
                onClick={handleGetRecommendation}
                disabled={recommending}
                title="Suggest which engine best fixes the issue you described"
              >
                {recommending ? "Checking..." : "Suggest a model"}
              </button>
              <button
                onClick={handleRegenerate}
                disabled={scene.status === "generating" || !feedback.trim()}
              >
                {scene.status === "generating"
                  ? "Generating..."
                  : "Regenerate with fix"}
              </button>
            </div>
            {recommendation && (
              <div className="cost-perf-view">
                {recommendation.issue_type && (
                  <p className="cost-perf-summary">
                    Issue detected: <strong>{recommendation.issue_type}</strong>
                  </p>
                )}
                {recommendation.candidates.map((c) => (
                  <div
                    key={c.id}
                    className={`cost-perf-row ${c.recommended ? "cost-perf-recommended" : ""}`}
                  >
                    <span className="cost-perf-label">
                      {c.recommended ? "★ " : ""}
                      {c.label}
                    </span>
                    <span className="cost-perf-score">score {c.score}</span>
                    <span className="cost-perf-time">
                      ~{Math.round(c.avg_seconds_per_image / 60)} min/image
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
