import { useState } from "react";

export default function NovellaSidebar({ novellas, activeNovellaId, onSelect, onHome }) {
  const [open, setOpen] = useState(false);

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
          {novellas.map((n) => (
            <li key={n.id}>
              <button
                className={`novella-sidebar-item ${
                  n.id === activeNovellaId ? "novella-sidebar-item-active" : ""
                }`}
                onClick={() => {
                  onSelect(n.id);
                  setOpen(false);
                }}
              >
                <span className="novella-sidebar-item-title">{n.title}</span>
                <span className={`status status-${n.status}`}>{n.status}</span>
                <span className="novella-sidebar-item-meta">
                  {n.scene_count} scene{n.scene_count === 1 ? "" : "s"}
                  {n.generating_count > 0 && ` · ${n.generating_count} generating`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </>
  );
}
