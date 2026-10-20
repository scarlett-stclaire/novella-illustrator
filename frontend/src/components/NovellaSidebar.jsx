import { useState } from "react";

export default function NovellaSidebar({
  novellas,
  activeNovellaId,
  onSelect,
  onHome,
  onDelete,
  onCancel,
}) {
  const [open, setOpen] = useState(false);
  const [busyId, setBusyId] = useState(null);
  // window.confirm() doesn't reliably work inside Tauri's webview (no native
  // dialog delegate wired up on the Rust side) - it silently does nothing,
  // which looked exactly like a dead button. Two-step in-UI confirmation
  // instead, so it behaves identically in the browser and the packaged app.
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

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
    <>
      <button
        type="button"
        className={`sidebar-toggle ${open ? "sidebar-toggle-open" : ""}`}
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close novella list" : "Open novella list"}
        aria-expanded={open}
      >
        <span className="sidebar-toggle-arrow">{open ? "‹" : "›"}</span>
        {!open && <span className="sidebar-toggle-label">Novellas</span>}
      </button>

      {open && (
        <div className="sidebar-backdrop" onClick={() => setOpen(false)} />
      )}

      <aside className={`novella-sidebar ${open ? "novella-sidebar-open" : ""}`}>
        <div className="novella-sidebar-header">
          <span>Your novellas</span>
          <button
            type="button"
            className="sidebar-home-link"
            onClick={() => {
              onHome();
              setOpen(false);
            }}
          >
            + New
          </button>
        </div>
        <ul className="novella-sidebar-list">
          {novellas.length === 0 && (
            <li className="novella-sidebar-empty">No novellas yet</li>
          )}
          {novellas.map((n) => {
            const isActive =
              n.status === "breaking_down" ||
              n.character_status === "extracting" ||
              n.generating_count > 0;
            return (
              <li key={n.id}>
                <button
                  className={`novella-sidebar-item ${
                    n.id === activeNovellaId ? "novella-sidebar-item-active" : ""
                  }`}
                  onClick={() => {
                    onSelect(n.id);
                    setOpen(false);
                    setConfirmDeleteId(null);
                  }}
                >
                  <span className="novella-sidebar-item-title">{n.title}</span>
                  <span className={`status status-${n.status}`}>{n.status}</span>
                  <span className="novella-sidebar-item-meta">
                    {n.scene_count} scene{n.scene_count === 1 ? "" : "s"}
                    {n.generating_count > 0 && ` · ${n.generating_count} generating`}
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
      </aside>
    </>
  );
}
