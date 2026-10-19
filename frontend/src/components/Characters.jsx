import { useState } from "react";
import { api, resolveAssetUrl } from "../api.js";
import Panel from "./Panel.jsx";

export default function Characters({
  novella,
  engines,
  textProviders,
  defaultTextProviderId,
  onUpdate,
}) {
  const [extracting, setExtracting] = useState(false);
  const [extractProviderId, setExtractProviderId] = useState("");
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSynopsis, setNewSynopsis] = useState("");
  const [newVisual, setNewVisual] = useState("");

  const availableEngines = (engines || []).filter((e) => e.available);
  const characters = novella.characters || [];

  async function handleExtract() {
    setExtracting(true);
    setError(null);
    try {
      const updated = await api.extractCharacters(novella.id, extractProviderId);
      onUpdate(updated);
    } catch (err) {
      setError(err.message);
      setExtracting(false);
    }
    // extraction runs in the background - the parent's polling effect will
    // pick up character_status transitioning to "ready"/"error"
  }

  async function handleAdd(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      const updated = await api.addCharacter(novella.id, {
        name: newName.trim(),
        synopsis: newSynopsis.trim(),
        visualDescription: newVisual.trim(),
      });
      onUpdate(updated);
      setNewName("");
      setNewSynopsis("");
      setNewVisual("");
      setShowAddForm(false);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleApplyToScenes() {
    setApplying(true);
    setError(null);
    try {
      const updated = await api.applyCharactersToScenes(novella.id);
      onUpdate(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="characters-section">
      <div className="characters-header">
        <h2>Characters</h2>
        <div className="characters-header-actions">
          {textProviders && textProviders.length > 0 && (
            <select
              value={extractProviderId}
              onChange={(e) => setExtractProviderId(e.target.value)}
            >
              <option value="">
                Default (
                {textProviders.find((p) => p.id === defaultTextProviderId)?.label ||
                  defaultTextProviderId}
                )
              </option>
              {textProviders
                .filter((p) => p.available)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
            </select>
          )}
          <button
            onClick={handleExtract}
            disabled={extracting || novella.character_status === "extracting"}
          >
            {novella.character_status === "extracting"
              ? "Finding characters…"
              : characters.length > 0
              ? "Re-scan for characters"
              : "Find characters"}
          </button>
          {characters.length > 0 && (
            <button onClick={handleApplyToScenes} disabled={applying}>
              {applying ? "Applying…" : "Lock appearances into scenes"}
            </button>
          )}
        </div>
      </div>

      <p className="settings-note">
        "Lock appearances into scenes" appends each character's visual
        description to every scene that mentions them by name, so hair/
        costume/build stay worded consistently across illustrations. This is
        a prompt-level consistency aid, not true image-conditioning - the
        model can still draw a different face each time.
      </p>

      {error && <p className="error">{error}</p>}
      {novella.character_status === "error" && novella.character_error && (
        <p className="error">{novella.character_error}</p>
      )}

      <div className="character-list">
        {characters.map((character) => (
          <CharacterCard
            key={character.id}
            novellaId={novella.id}
            character={character}
            engines={availableEngines}
            onUpdate={onUpdate}
          />
        ))}
      </div>

      {showAddForm ? (
        <form className="add-scene-form" onSubmit={handleAdd}>
          <input
            type="text"
            placeholder="Character name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <textarea
            placeholder="Synopsis - who they are, their role in the story"
            value={newSynopsis}
            onChange={(e) => setNewSynopsis(e.target.value)}
            rows={2}
          />
          <textarea
            placeholder="Visual description - hair, build, clothing, distinguishing features"
            value={newVisual}
            onChange={(e) => setNewVisual(e.target.value)}
            rows={2}
          />
          <div className="add-scene-actions">
            <button type="submit">Add character</button>
            <button type="button" onClick={() => setShowAddForm(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button className="add-scene-trigger" onClick={() => setShowAddForm(true)}>
          + Add a character Novella missed
        </button>
      )}
    </div>
  );
}

function CharacterCard({ novellaId, character, engines, onUpdate }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(character.name);
  const [synopsis, setSynopsis] = useState(character.synopsis);
  const [visual, setVisual] = useState(character.visual_description);
  const [engineId, setEngineId] = useState(
    character.engine_id || engines[0]?.id || ""
  );
  const [busy, setBusy] = useState(false);

  async function handleSave() {
    setBusy(true);
    try {
      const updated = await api.updateCharacter(novellaId, character.id, {
        name,
        synopsis,
        visualDescription: visual,
      });
      onUpdate(updated);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    setBusy(true);
    try {
      const updated = await api.deleteCharacter(novellaId, character.id);
      onUpdate(updated);
    } catch {
      setBusy(false);
    }
  }

  async function handleUploadImage(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const updated = await api.uploadCharacterImage(novellaId, character.id, file);
      onUpdate(updated);
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerateImage() {
    setBusy(true);
    try {
      const updated = await api.generateCharacterImage(
        novellaId,
        character.id,
        engineId
      );
      onUpdate(updated);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="scene-card character-card">
      <div className="scene-header">
        {character.name}
        <span className={`status status-${character.status}`}>
          {character.status}
        </span>
        {character.manual && <span className="status status-manual">manual</span>}
      </div>

      <Panel
        scene="candle"
        image={resolveAssetUrl(character.image_path)}
        alt={character.name}
        ghostLabel={!character.image_path ? "NO PORTRAIT YET" : undefined}
      />

      {!editing ? (
        <>
          <p className="scene-summary">{character.synopsis || "No synopsis yet."}</p>
          {character.visual_description && (
            <p className="scene-recommendation">{character.visual_description}</p>
          )}
          <div className="scene-actions">
            <button onClick={() => setEditing(true)}>Edit</button>
            <button className="delete-btn" onClick={handleDelete} disabled={busy}>
              Delete
            </button>
          </div>
        </>
      ) : (
        <>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} />
          <textarea
            value={synopsis}
            onChange={(e) => setSynopsis(e.target.value)}
            rows={2}
            placeholder="Synopsis"
          />
          <textarea
            value={visual}
            onChange={(e) => setVisual(e.target.value)}
            rows={2}
            placeholder="Visual description"
          />
          <div className="scene-actions">
            <button onClick={handleSave} disabled={busy}>
              Save
            </button>
            <button onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </>
      )}

      {character.status === "generating" && (
        <div className="scene-progress">
          {character.progress ? (
            <>
              <progress value={character.progress.value} max={character.progress.max} />
              <span>
                step {character.progress.value}/{character.progress.max}
              </span>
            </>
          ) : (
            <span>queued…</span>
          )}
        </div>
      )}
      {character.error && <p className="scene-error">{character.error}</p>}

      <div className="scene-feedback-actions">
        <input type="file" accept="image/*" onChange={handleUploadImage} disabled={busy} />
        {engines.length > 0 && (
          <select value={engineId} onChange={(e) => setEngineId(e.target.value)}>
            {engines.map((e) => (
              <option key={e.id} value={e.id}>
                {e.label}
              </option>
            ))}
          </select>
        )}
        <button
          onClick={handleGenerateImage}
          disabled={busy || character.status === "generating"}
        >
          {character.image_path ? "Regenerate" : "Generate portrait"}
        </button>
      </div>
    </div>
  );
}
