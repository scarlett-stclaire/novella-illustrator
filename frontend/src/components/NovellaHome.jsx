import { useState } from "react";

export default function NovellaHome({ novellas, onSelect, onDelete, onCancel }) {
  const [busyId, setBusyId] = useState(null);
  // window.confirm() doesn't reliably work inside Tauri's webview (no native
  // dialog delegate wired up on the Rust side) - it silently does nothing,
  // which looked exactly like a dead button. Two-step in-UI confirmation
  // instead, so it behaves identically in the browser and the packaged app.
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  if (!novellas.length) return null;

  async function handleDeleteClick(e, novella) {
    e.stopPropagation();
    if (confirmDeleteId !== novella.id) {
      setConfirmDeleteId(novella.id);
      return;
    }
    setConfirmDeleteId(null);
    setBusyId(novella.id);
    try {
      await onDelete(novella.id);
    } finally {
      setBusyId(null);
    }
  }

  function handleCancelDeleteClick(e) {
    e.stopPropagation();
    setConfirmDeleteId(null);
  }

  async function handleCancelClick(e, novella) {
    e.stopPropagation();
    setBusyId(novella.id);
    try {
      await onCancel(novella.id);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="novella-home-list">
      <h2>Your novellas</h2>
      <ul>
        {novellas.map((n) => {
          const isActive =
            n.status === "breaking_down" ||
            n.character_status === "extracting" ||
            n.generating_count > 0;
          return (
            <li key={n.id}>
              <button
                className="novella-link"
                onClick={() => {
                  onSelect(n.id);
                  setConfirmDeleteId(null);
                }}
              >
                <span className="novella-link-title">{n.title}</span>
                <span className={`status status-${n.status}`}>{n.status}</span>
                <span className="novella-link-meta">
                  {n.scene_count} scene{n.scene_count === 1 ? "" : "s"}
                  {n.generating_count > 0 &&
                    ` · ${n.generating_count} generating`}
                </span>
              </button>
              <div className="novella-sidebar-item-actions">
                {isActive && (
                  <button
                    type="button"
                    className="novella-sidebar-action"
                    disabled={busyId === n.id}
                    onClick={(e) => handleCancelClick(e, n)}
                    title="Stop whatever's currently running for this novella"
                  >
                    Stop
                  </button>
                )}
                {confirmDeleteId === n.id && (
                  <button
                    type="button"
                    className="novella-sidebar-action"
                    onClick={handleCancelDeleteClick}
                  >
                    Cancel
                  </button>
                )}
                <button
                  type="button"
                  className="novella-sidebar-action novella-sidebar-action-delete"
                  disabled={busyId === n.id}
                  onClick={(e) => handleDeleteClick(e, n)}
                  title="Delete this novella"
                >
                  {confirmDeleteId === n.id ? "Confirm delete?" : "Delete"}
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
