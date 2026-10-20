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
import WorkflowBar from "./components/WorkflowBar.jsx";

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
    // On a cold launch of the packaged app, the frontend renders instantly
    // but the backend/ComfyUI it talks to are still starting up (ComfyUI
    // alone took ~10-15s in testing) - a single one-shot fetch here would
    // race that startup and lock the UI into a false "unavailable" state for
    // the rest of the session. health is a live status, not a one-time
    // snapshot, so poll it indefinitely rather than giving up after N tries
    // - this also lets the header reflect ComfyUI going down later, not just
    // coming up at launch. engines/textProviders only depend on the backend
    // itself (not ComfyUI's slower startup), so a bounded retry is enough
    // for those; the dev-server case (everything already running) succeeds
    // on the first try either way, so none of this changes that behavior.
    let cancelled = false;
    async function loadWithRetry(fn, onSuccess, attempts = 8, delayMs = 2000) {
      for (let i = 0; i < attempts; i++) {
        try {
          const data = await fn();
          if (!cancelled) onSuccess(data);
          return;
        } catch {
          if (i < attempts - 1) await new Promise((r) => setTimeout(r, delayMs));
        }
      }
    }
    async function pollHealth() {
      while (!cancelled) {
        try {
          const data = await api.health();
          if (!cancelled) setHealth(data);
        } catch {
          if (!cancelled) setHealth({ ollama: false, comfyui: false });
        }
        await new Promise((r) => setTimeout(r, 3000));
      }
    }
    pollHealth();
    loadWithRetry(api.listEngines, setEngines);
    loadWithRetry(api.listTextProviders, (data) => {
      setTextProviders(data.providers);
      setDefaultTextProviderId(data.default_provider_id);
    });
    return () => {
      cancelled = true;
    };
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

  // A chunk can take minutes with a large local model and the chunk-count
  // progress bar only moves between whole chunks, so a single-chunk story
  // (the common case) shows flat "starting..." text for the entire wait -
  // reads as frozen even though it's working. An elapsed-time counter at
  // least shows it's alive; see also the workflow bar below for overall
  // stage context during the same wait.
  const [breakdownElapsed, setBreakdownElapsed] = useState(0);
  useEffect(() => {
    if (!breakingDown) {
      setBreakdownElapsed(0);
      return;
    }
    const start = Date.now();
    const interval = setInterval(() => {
      setBreakdownElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [breakingDown]);

  const hasScenes = (novella?.scenes.length ?? 0) > 0;
  const hasCharacters =
    novella?.character_status === "ready" || (novella?.characters?.length ?? 0) > 0;
  const anyImageDone = novella?.scenes.some((s) => s.image_path) ?? false;
  const allImagesDone = hasScenes && novella.scenes.every((s) => s.image_path);

  const workflowStages = novella
    ? [
        { id: "story", label: "Story", status: "done" },
        {
          id: "breakdown",
          label: "Breakdown",
          status:
            novella.status === "error"
              ? "error"
              : breakingDown
              ? "active"
              : hasScenes
              ? "done"
              : "pending",
          hint: "Scene breakdown",
        },
        {
          id: "characters",
          label: "Characters",
          status: extractingCharacters
            ? "active"
            : novella.character_status === "error"
            ? "error"
            : hasCharacters
            ? "done"
            : "pending",
          hint: "Click to open the Characters panel",
        },
        {
          id: "illustrate",
          label: "Illustrate",
          status: anyGenerating
            ? "active"
            : allImagesDone
            ? "done"
            : anyImageDone
            ? "active"
            : "pending",
          hint: "Scroll to the scene list to generate images",
        },
        {
          id: "publish",
          label: "Publish",
          status: showPublish ? "active" : "pending",
          locked: !anyImageDone,
          hint: anyImageDone
            ? "Click to open the Publish panel"
            : "Generate at least one scene image first",
        },
      ]
    : [];

  function handleWorkflowStageClick(stageId) {
    if (stageId === "characters") setShowCharacters(true);
    if (stageId === "illustrate") {
      setShowCharacters(false);
      setShowPublish(false);
      document
        .querySelector(".scene-list")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (stageId === "publish" && anyImageDone) setShowPublish(true);
  }

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

          <WorkflowBar stages={workflowStages} onStageClick={handleWorkflowStageClick} />

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
              <p>
                <span className="breakdown-spinner" aria-hidden="true" />
                Breaking the story into scenes…
              </p>
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
                <span>
                  {breakdownElapsed < 5
                    ? "starting…"
                    : `still working… (${breakdownElapsed}s - large local models can take a few minutes per chunk)`}
                </span>
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
