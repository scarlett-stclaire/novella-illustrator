export default function NovellaHome({ novellas, onSelect }) {
  if (!novellas.length) return null;

  return (
    <div className="novella-home-list">
      <h2>Your novellas</h2>
      <ul>
        {novellas.map((n) => (
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
          </li>
        ))}
      </ul>
    </div>
  );
}
