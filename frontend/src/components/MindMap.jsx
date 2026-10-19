import { useState } from "react";
import { api } from "../api.js";

/**
 * A lightweight editable "mind map" of the story's chunks (F11): each scene
 * is a connected node in reading order, with reorder/merge/split/rename
 * controls (F25) that act on the same scene list the chunk/review views
 * show - editing here updates the chunks everywhere else, since it's the
 * same underlying data, not a separate graph.
 *
 * Deliberately not built on a node-graph library (e.g. React Flow): the
 * spec's own behaviour notes define "mind map editing" as exactly these
 * four operations on an ordered list, not free-form 2D node placement, so
 * a connected-flow layout satisfies F11 without a new heavy dependency.
 */
export default function MindMap({ novella, onUpdate }) {
  const scenes = novella.scenes;

  async function handleMove(sceneId, direction) {
    const updated = await api.moveScene(novella.id, sceneId, direction);
    onUpdate(updated);
  }

  async function handleMerge(sceneId) {
    const updated = await api.mergeSceneNext(novella.id, sceneId);
    onUpdate(updated);
  }

  async function handleRename(sceneId, summary) {
    const updated = await api.updateScene(novella.id, sceneId, { summary });
    onUpdate(updated);
  }

  async function handleSplit(sceneId, parts) {
    const updated = await api.splitScene(novella.id, sceneId, parts);
    onUpdate(updated);
  }

  if (scenes.length === 0) {
    return <p className="settings-note">No chunks yet - break the story down first.</p>;
  }

  return (
    <div className="mind-map">
      {scenes.map((scene, i) => (
        <div className="mind-map-node-wrap" key={scene.id}>
          <MindMapNode
            scene={scene}
            isFirst={i === 0}
            isLast={i === scenes.length - 1}
            onMove={handleMove}
            onMerge={handleMerge}
            onRename={handleRename}
            onSplit={handleSplit}
          />
          {i < scenes.length - 1 && <span className="mind-map-arrow">→</span>}
        </div>
      ))}
    </div>
  );
}

function MindMapNode({ scene, isFirst, isLast, onMove, onMerge, onRename, onSplit }) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(scene.summary);
  const [splitting, setSplitting] = useState(false);
  const [summaryA, setSummaryA] = useState(scene.summary);
  const [promptA, setPromptA] = useState(scene.image_prompt);
  const [summaryB, setSummaryB] = useState("");
  const [promptB, setPromptB] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleRenameSave() {
    setBusy(true);
    try {
      await onRename(scene.id, name);
      setRenaming(false);
    } finally {
      setBusy(false);
    }
  }

  async function handleSplitSave() {
    setBusy(true);
    try {
      await onSplit(scene.id, {
        summaryA,
        promptA,
        summaryB,
        promptB,
      });
      setSplitting(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mind-map-node">
      <div className="mind-map-node-header">
        <span className="scene-tag">chunk {scene.index + 1}</span>
        {scene.scene_type && <span className="scene-tag">{scene.scene_type.replace("_", " ")}</span>}
      </div>

      {!renaming ? (
        <p className="mind-map-node-label" onClick={() => setRenaming(true)}>
          {scene.summary}
        </p>
      ) : (
        <div className="mind-map-rename">
          <textarea value={name} onChange={(e) => setName(e.target.value)} rows={2} />
          <div className="add-scene-actions">
            <button onClick={handleRenameSave} disabled={busy}>
              Save
            </button>
            <button onClick={() => setRenaming(false)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="mind-map-node-actions">
        <button onClick={() => onMove(scene.id, "up")} disabled={isFirst} title="Move earlier">
          ↑
        </button>
        <button onClick={() => onMove(scene.id, "down")} disabled={isLast} title="Move later">
          ↓
        </button>
        <button onClick={() => onMerge(scene.id)} disabled={isLast} title="Merge with next chunk">
          Merge →
        </button>
        <button onClick={() => setSplitting((v) => !v)}>Split</button>
      </div>

      {splitting && (
        <div className="mind-map-split-form">
          <label className="scene-count-field">
            First chunk
            <textarea value={summaryA} onChange={(e) => setSummaryA(e.target.value)} rows={2} placeholder="Summary" />
            <textarea value={promptA} onChange={(e) => setPromptA(e.target.value)} rows={2} placeholder="Image prompt" />
          </label>
          <label className="scene-count-field">
            Second chunk
            <textarea value={summaryB} onChange={(e) => setSummaryB(e.target.value)} rows={2} placeholder="Summary" />
            <textarea value={promptB} onChange={(e) => setPromptB(e.target.value)} rows={2} placeholder="Image prompt" />
          </label>
          <div className="add-scene-actions">
            <button
              onClick={handleSplitSave}
              disabled={busy || !summaryB.trim() || !promptB.trim()}
            >
              Split into two
            </button>
            <button onClick={() => setSplitting(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
