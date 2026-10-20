import { useState } from "react";

export default function NovellaHome({ novellas, onSelect, onDelete, onCancel }) {
  const [busyId, setBusyId] = useState(null);

  if (!novellas.length) return null;

  async function handleDeleteClick(e, novella) {
    e.stopPropagation();
    if (!window.confirm(`Delete "${novella.title}"? This can't be undone.`)) return;
    setBusyId(novella.id);
    try {
      await onDelete(novella.id);
    } finally {
      setBusyId(null);
    }
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
              <button className="novella-link" onClick={() => onSelect(n.id)}>
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
                <button
                  type="button"
                  className="novella-sidebar-action novella-sidebar-action-delete"
                  disabled={busyId === n.id}
                  onClick={(e) => handleDeleteClick(e, n)}
                  title="Delete this novella"
                >
                  Delete
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
