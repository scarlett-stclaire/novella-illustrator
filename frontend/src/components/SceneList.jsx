import SceneCard from "./SceneCard.jsx";
import AddSceneRow from "./AddSceneRow.jsx";

export default function SceneList({
  scenes,
  engines,
  onSavePrompt,
  onGenerate,
  onRegenerate,
  onAddScene,
  onDeleteScene,
}) {
  return (
    <div className="scene-list">
      <AddSceneRow afterSceneId={null} onAdd={onAddScene} />
      {scenes.map((scene) => (
        <div key={scene.id}>
          <SceneCard
            scene={scene}
            engines={engines}
            onSavePrompt={onSavePrompt}
            onGenerate={onGenerate}
            onRegenerate={onRegenerate}
            onDelete={onDeleteScene}
          />
          <AddSceneRow afterSceneId={scene.id} onAdd={onAddScene} />
        </div>
      ))}
    </div>
  );
}
