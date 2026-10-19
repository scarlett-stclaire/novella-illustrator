import { useState } from "react";

export default function AddSceneRow({ afterSceneId, onAdd }) {
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState("");
  const [imagePrompt, setImagePrompt] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleAdd() {
    if (!summary.trim() || !imagePrompt.trim()) return;
    setSaving(true);
    try {
      await onAdd({
        summary: summary.trim(),
        imagePrompt: imagePrompt.trim(),
        afterSceneId,
      });
      setSummary("");
      setImagePrompt("");
      setOpen(false);
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button type="button" className="add-scene-trigger" onClick={() => setOpen(true)}>
        + Add scene here
      </button>
    );
  }

  return (
    <div className="add-scene-form">
      <textarea
        placeholder="Scene summary"
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        rows={2}
      />
      <textarea
        placeholder="Image prompt"
        value={imagePrompt}
        onChange={(e) => setImagePrompt(e.target.value)}
        rows={2}
      />
      <div className="add-scene-actions">
        <button onClick={handleAdd} disabled={saving}>
          {saving ? "Adding..." : "Add"}
        </button>
        <button onClick={() => setOpen(false)} disabled={saving}>
          Cancel
        </button>
      </div>
    </div>
  );
}
