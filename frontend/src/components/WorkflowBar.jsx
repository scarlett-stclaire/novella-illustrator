const STATUS_SYMBOL = {
  done: "✓",
  active: "…",
  error: "!",
  pending: "",
};

export default function WorkflowBar({ stages, onStageClick }) {
  return (
    <div className="workflow-bar" role="list">
      {stages.map((stage, i) => (
        <button
          key={stage.id}
          type="button"
          role="listitem"
          className={`workflow-step workflow-step-${stage.status}`}
          onClick={() => onStageClick?.(stage.id)}
          disabled={stage.locked}
          title={stage.hint}
        >
          <span className="workflow-step-marker">
            {STATUS_SYMBOL[stage.status] || i + 1}
          </span>
          <span className="workflow-step-label">{stage.label}</span>
          {i < stages.length - 1 && (
            <span className="workflow-step-connector" aria-hidden="true" />
          )}
        </button>
      ))}
    </div>
  );
}
