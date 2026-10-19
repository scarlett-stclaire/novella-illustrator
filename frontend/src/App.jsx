import { useEffect, useState } from "react";
import { api } from "./api.js";
import UploadForm from "./components/UploadForm.jsx";
import SceneList from "./components/SceneList.jsx";
import SourceCoverage from "./components/SourceCoverage.jsx";
import NovellaHome from "./components/NovellaHome.jsx";
import Settings from "./components/Settings.jsx";
import Characters from "./components/Characters.jsx";
import MindMap from "./components/MindMap.jsx";
import Publish from "./components/Publish.jsx";

function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function novellaIdFromUrl() {
  const match = window.location.pathname.match(/^\/novella\/([^/]+)/);
  return match ? match[1] : null;
}

export default function App() {
  const [novellaId, setNovellaId] = useState(novellaIdFromUrl());
  const [isSettingsRoute, setIsSettingsRoute] = useState(
    window.location.pathname === "/settings"
  );
  const [novella, setNovella] = useState(null);
  const [novellas, setNovellas] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [health, setHealth] = useState(null);
  const [showCoverage, setShowCoverage] = useState(false);
  const [showCharacters, setShowCharacters] = useState(false);
  const [showMindMap, setShowMindMap] = useState(false);
  const [showPublish, setShowPublish] = useState(false);
  const [showCostPerf, setShowCostPerf] = useState(false);
  const [costPerf, setCostPerf] = useState(null);
  const [engines, setEngines] = useState([]);
  const [textProviders, setTextProviders] = useState([]);
  const [defaultTextProviderId, setDefaultTextProviderId] = useState("ollama");

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ollama: false, comfyui: false }));
    api.listEngines().then(setEngines).catch(() => setEngines([]));
    api
      .listTextProviders()
      .then((data) => {
        setTextProviders(data.providers);
        setDefaultTextProviderId(data.default_provider_id);
      })
      .catch(() => setTextProviders([]));
  }, []);

  useEffect(() => {
    function syncFromUrl() {
      setNovellaId(novellaIdFromUrl());
      setIsSettingsRoute(window.location.pathname === "/settings");
    }
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, []);

  useEffect(() => {
    setShowCoverage(false);
    setShowCostPerf(false);
    setCostPerf(null);
    setError(null);
    if (!novellaId) {
      setNovella(null);
      api.listNovellas().then(setNovellas).catch(() => {});
      return;
    }
    api
      .getNovella(novellaId)
      .then(setNovella)
      .catch((err) => {
        setError(err.message);
        setNovella(null);
      });
  }, [novellaId]);

  const anyGenerating = novella?.scenes.some((s) => s.status === "generating") ?? false;
  const breakingDown = novella?.status === "breaking_down";
  const extractingCharacters = novella?.character_status === "extracting";
  const anyCharacterGenerating =
    novella?.characters?.some((c) => c.status === "generating") ?? false;

  useEffect(() => {
    if (
      !novella ||
      (!anyGenerating && !breakingDown && !extractingCharacters && !anyCharacterGenerating)
    )
      return;
    const interval = setInterval(async () => {
      try {
        const updated = await api.getNovella(novella.id);
        setNovella(updated);
      } catch {
        // transient poll failure - next tick will retry
      }
    }, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [novella?.id, anyGenerating, breakingDown, extractingCharacters, anyCharacterGenerating]);

  async function handleCreate(title, text, targetSceneCount, textProviderId) {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createNovella(title, text, targetSceneCount);
      await api.breakdown(created.id, textProviderId);
      navigate(`/novella/${created.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleAddScene({ summary, imagePrompt, afterSceneId }) {
    const updated = await api.addScene(novella.id, {
      summary,
      imagePrompt,
      afterSceneId,
    });
    setNovella(updated);
  }

  async function handleDeleteScene(sceneId) {
    const updated = await api.deleteScene(novella.id, sceneId);
    setNovella(updated);
  }

  async function handleSavePrompt(sceneId, imagePrompt) {
    const updated = await api.updateScenePrompt(novella.id, sceneId, imagePrompt);
    setNovella(updated);
  }

  async function handleGenerate(sceneId, engineId) {
    setNovella((prev) => ({
      ...prev,
      scenes: prev.scenes.map((s) =>
        s.id === sceneId ? { ...s, status: "generating" } : s
      ),
    }));
    try {
      const updated = await api.generateSceneImage(novella.id, sceneId, engineId);
      setNovella(updated);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleToggleCostPerf() {
    if (showCostPerf) {
      setShowCostPerf(false);
      return;
    }
    setShowCostPerf(true);
    if (!costPerf) {
      try {
        const data = await api.getNovellaCostPerf(novella.id);
        setCostPerf(data);
      } catch (err) {
        setError(err.message);
      }
    }
  }

  async function handleRegenerate(sceneId, feedback, engineId) {
    setNovella((prev) => ({
      ...prev,
      scenes: prev.scenes.map((s) =>
        s.id === sceneId ? { ...s, status: "generating" } : s
      ),
    }));
    try {
      const updated = await api.regenerateSceneImage(
        novella.id,
        sceneId,
        feedback,
        engineId
      );
      setNovella(updated);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="app">
      <nav className="app-nav">
        <button className="home-link wordmark" onClick={() => navigate("/")}>
          <span className="wordmark-script">Novella</span>
          <span className="wordmark-sans">Illustrator</span>
        </button>
        <div className="nav-links">
          <button className="home-link settings-link" onClick={() => navigate("/settings")}>
            Settings
          </button>
        </div>
      </nav>

      <div className="app-content">
        {health && (
          <p className="health">
            LLM: {health.ollama ? "ready" : "unavailable"} · Image gen:{" "}
            {health.comfyui ? "ready" : "unavailable"}
          </p>
        )}
        {error && <p className="error">{error}</p>}

        {isSettingsRoute && <Settings />}

      {!isSettingsRoute && !novellaId && (
        <>
          <UploadForm
            onSubmit={handleCreate}
            busy={busy}
            providers={textProviders}
            defaultProviderId={defaultTextProviderId}
          />
          <NovellaHome
            novellas={novellas}
            onSelect={(id) => navigate(`/novella/${id}`)}
          />
        </>
      )}

      {!isSettingsRoute && novellaId && novella && (
        <>
          <h2>{novella.title}</h2>
          <button onClick={() => navigate("/")}>Back to all novellas</button>

          {novella.recommended_engine_id && (
            <div className="story-recommendation">
              <p>
                Story reads as <strong>{novella.scene_type?.replace("_", " ")}</strong>,{" "}
                <strong>{novella.complexity}</strong> complexity. Recommended
                engine:{" "}
                <strong>
                  {engines.find((e) => e.id === novella.recommended_engine_id)?.label ??
                    novella.recommended_engine_id}
                </strong>
              </p>
              <button onClick={handleToggleCostPerf}>
                {showCostPerf ? "Hide" : "Show"} cost/performance comparison
              </button>
              {showCostPerf && costPerf && (
                <div className="cost-perf-view">
                  {costPerf.candidates.map((c) => (
                    <div
                      key={c.id}
                      className={`cost-perf-row ${c.recommended ? "cost-perf-recommended" : ""}`}
                    >
                      <span className="cost-perf-label">
                        {c.recommended ? "★ " : ""}
                        {c.label}
                      </span>
                      <span className="cost-perf-score">score {c.score}</span>
                      <span className="cost-perf-time">
                        ~{Math.round(c.avg_seconds_per_image / 60)} min/image
                      </span>
                      <span className="cost-perf-notes">{c.notes}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {breakingDown && (
            <div className="breakdown-progress">
              <p>Breaking the story into scenes…</p>
              {novella.breakdown_progress ? (
                <>
                  <progress
                    value={novella.breakdown_progress.value}
                    max={novella.breakdown_progress.max}
                  />
                  <span>
                    chunk {novella.breakdown_progress.value}/
                    {novella.breakdown_progress.max}
                  </span>
                </>
              ) : (
                <span>starting…</span>
              )}
            </div>
          )}
          {novella.status === "error" && novella.breakdown_error && (
            <p className="error">{novella.breakdown_error}</p>
          )}

          {novella.scenes.length > 0 && (
            <button onClick={() => setShowCoverage((v) => !v)}>
              {showCoverage ? "Hide source coverage" : "Show source coverage"}
            </button>
          )}
          {showCoverage && (
            <SourceCoverage text={novella.text} scenes={novella.scenes} />
          )}

          <button onClick={() => setShowCharacters((v) => !v)}>
            {showCharacters ? "Hide characters" : "Characters"}
            {novella.characters?.length > 0 ? ` (${novella.characters.length})` : ""}
          </button>
          {showCharacters && (
            <Characters
              novella={novella}
              engines={engines}
              textProviders={textProviders}
              defaultTextProviderId={defaultTextProviderId}
              onUpdate={setNovella}
            />
          )}

          {novella.scenes.length > 0 && (
            <button onClick={() => setShowMindMap((v) => !v)}>
              {showMindMap ? "Hide mind map" : "Show mind map"}
            </button>
          )}
          {showMindMap && <MindMap novella={novella} onUpdate={setNovella} />}

          {novella.scenes.some((s) => s.image_path) && (
            <button onClick={() => setShowPublish((v) => !v)}>
              {showPublish ? "Hide publish" : "Publish"}
            </button>
          )}
          {showPublish && <Publish novellaId={novella.id} />}

          <SceneList
            novellaId={novella.id}
            scenes={novella.scenes}
            engines={engines}
            onSavePrompt={handleSavePrompt}
            onGenerate={handleGenerate}
            onRegenerate={handleRegenerate}
            onAddScene={handleAddScene}
            onDeleteScene={handleDeleteScene}
          />
        </>
      )}
      </div>
    </div>
  );
}
