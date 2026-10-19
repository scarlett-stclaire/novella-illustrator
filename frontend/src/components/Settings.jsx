import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Settings() {
  const [providers, setProviders] = useState([]);
  const [defaultProviderId, setDefaultProviderId] = useState("ollama");
  const [keyInputs, setKeyInputs] = useState({});
  const [busyProvider, setBusyProvider] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [catalogue, setCatalogue] = useState([]);
  const [engines, setEngines] = useState([]);
  const [engineBusy, setEngineBusy] = useState(false);
  const [storageInfo, setStorageInfo] = useState(null);
  const [storagePathInput, setStoragePathInput] = useState("");
  const [storageBusy, setStorageBusy] = useState(false);
  const [ollamaModels, setOllamaModels] = useState([]);
  const [selectedOllamaModel, setSelectedOllamaModel] = useState("");
  const [ollamaModelBusy, setOllamaModelBusy] = useState(false);

  async function refresh() {
    const [providersData, catalogueData, enginesData, storageData, ollamaModelsData] =
      await Promise.all([
        api.listTextProviders(),
        api.listCatalogue(),
        api.listSettingsEngines(),
        api.getStorageSettings(),
        api.listOllamaModels(),
      ]);
    setProviders(providersData.providers);
    setDefaultProviderId(providersData.default_provider_id);
    setCatalogue(catalogueData.models);
    setEngines(enginesData.engines);
    setStorageInfo(storageData);
    setStoragePathInput(storageData.saved_override || "");
    setOllamaModels(ollamaModelsData.models);
    setSelectedOllamaModel(ollamaModelsData.selected);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function handleSaveKey(providerId) {
    const apiKey = (keyInputs[providerId] || "").trim();
    if (!apiKey) return;
    setBusyProvider(providerId);
    setError(null);
    setNotice(null);
    try {
      await api.saveProviderKey(providerId, apiKey);
      setKeyInputs((prev) => ({ ...prev, [providerId]: "" }));
      setNotice(`Key saved for ${providerId}.`);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyProvider(null);
    }
  }

  async function handleRemoveKey(providerId) {
    setBusyProvider(providerId);
    setError(null);
    setNotice(null);
    try {
      await api.deleteProviderKey(providerId);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyProvider(null);
    }
  }

  async function handleSetDefault(providerId) {
    setError(null);
    try {
      await api.setDefaultProvider(providerId);
      setDefaultProviderId(providerId);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleToggleEngine(engineId, nextChecked) {
    setEngineBusy(true);
    setError(null);
    try {
      const nextIds = engines
        .filter((e) => (e.id === engineId ? nextChecked : e.enabled))
        .map((e) => e.id);
      await api.setEnabledEngines(nextIds);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setEngineBusy(false);
    }
  }

  async function handleSaveStorage() {
    setStorageBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.setStorageRoot(storagePathInput.trim());
      setNotice(
        "Storage location saved. Restart the app (quit and reopen, or re-run scripts/start.sh) for it to take effect."
      );
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setStorageBusy(false);
    }
  }

  async function handleSelectOllamaModel(model) {
    setOllamaModelBusy(true);
    setError(null);
    try {
      await api.setOllamaModel(model);
      setSelectedOllamaModel(model);
    } catch (err) {
      setError(err.message);
    } finally {
      setOllamaModelBusy(false);
    }
  }

  return (
    <div className="settings">
      <h2>Settings</h2>
      <p className="settings-note">
        API keys are stored in a machine-local file
        (<code>~/.novella-illustrator/settings.json</code>) outside this
        project's folder - never committed to git, never sent anywhere except
        the provider you choose below.
      </p>
      {error && <p className="error">{error}</p>}
      {notice && <p className="settings-notice">{notice}</p>}

      <h2>Storage location</h2>
      <p className="settings-note">
        Where projects, generated images and exports are saved. Currently:{" "}
        <code>{storageInfo?.active_root}</code>
        {storageInfo?.saved_override &&
          storageInfo.saved_override !== storageInfo.active_root && (
            <>
              {" "}
              (a new location is saved but not active yet - restart to switch
              to <code>{storageInfo.saved_override}</code>)
            </>
          )}
        . Changing this does not move existing data - it only changes where
        new data is written after a restart.
      </p>
      <div className="storage-location-row">
        <input
          type="text"
          placeholder="/path/to/folder (leave blank for the default)"
          value={storagePathInput}
          onChange={(e) => setStoragePathInput(e.target.value)}
        />
        <button onClick={handleSaveStorage} disabled={storageBusy}>
          {storageBusy ? "Saving..." : "Save"}
        </button>
      </div>

      <div className="provider-list">
        {providers.map((p) => (
          <div key={p.id} className="provider-row">
            <div className="provider-row-header">
              <strong>{p.label}</strong>
              <span
                className={`status ${p.available ? "status-done" : "status-error"}`}
              >
                {p.available ? "available" : "unavailable"}
              </span>
              <label className="provider-default">
                <input
                  type="radio"
                  name="default-provider"
                  checked={defaultProviderId === p.id}
                  onChange={() => handleSetDefault(p.id)}
                />
                default
              </label>
            </div>

            {p.requires_api_key && (
              <div className="provider-key-row">
                {p.has_key ? (
                  <>
                    <span className="provider-masked-key">{p.masked_key}</span>
                    <button
                      onClick={() => handleRemoveKey(p.id)}
                      disabled={busyProvider === p.id}
                    >
                      Remove key
                    </button>
                  </>
                ) : (
                  <>
                    <input
                      type="password"
                      placeholder="Paste API key"
                      value={keyInputs[p.id] || ""}
                      onChange={(e) =>
                        setKeyInputs((prev) => ({ ...prev, [p.id]: e.target.value }))
                      }
                    />
                    <button
                      onClick={() => handleSaveKey(p.id)}
                      disabled={busyProvider === p.id || !(keyInputs[p.id] || "").trim()}
                    >
                      {busyProvider === p.id ? "Validating..." : "Save key"}
                    </button>
                  </>
                )}
              </div>
            )}

            {p.id === "ollama" && (
              <div className="provider-key-row">
                <select
                  value={selectedOllamaModel}
                  disabled={ollamaModelBusy || ollamaModels.length === 0}
                  onChange={(e) => handleSelectOllamaModel(e.target.value)}
                >
                  {ollamaModels.length === 0 && <option>No models installed</option>}
                  {ollamaModels.map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.name}
                      {m.size_bytes
                        ? ` (${(m.size_bytes / 1e9).toFixed(1)} GB)`
                        : ""}
                    </option>
                  ))}
                </select>
                <span className="settings-note" style={{ margin: 0 }}>
                  used for story breakdown and character extraction
                </span>
              </div>
            )}
          </div>
        ))}
      </div>

      <h2>Image generation models</h2>
      <p className="settings-note">
        Only checked models are offered when generating or regenerating a
        scene's image. A model stays listed even when its weights aren't
        installed yet, so you can see what's available to download.
      </p>
      <div className="engine-list">
        {engines.map((e) => (
          <div key={e.id} className="engine-row">
            <label className="engine-row-header">
              <input
                type="checkbox"
                checked={e.enabled}
                disabled={engineBusy}
                onChange={(ev) => handleToggleEngine(e.id, ev.target.checked)}
              />
              <strong>{e.label}</strong>
              <span
                className={`status ${e.available ? "status-done" : "status-error"}`}
              >
                {e.available ? "installed" : "not installed"}
              </span>
            </label>
          </div>
        ))}
      </div>

      <h2>Open-source models</h2>
      <p className="settings-note">
        Downloaded by hand for now (no in-app downloader yet) - each entry
        shows the command used to fetch it. See the README for full details.
      </p>
      <div className="catalogue-list">
        {catalogue.map((m) => (
          <div key={m.id} className="catalogue-row">
            <div className="catalogue-row-header">
              <strong>{m.display_name}</strong>
              <span className="catalogue-task-type">{m.task_type}</span>
              <span
                className={`status ${m.installed ? "status-done" : "status-error"}`}
              >
                {m.installed ? "installed" : "not installed"}
              </span>
              <span className="catalogue-size">{m.download_size_gb} GB</span>
            </div>
            <p className="catalogue-description">{m.description}</p>
            <p className="catalogue-meta">
              {m.license}
              {m.requires_account && " · requires a free account on the source site"}
              {" · "}
              <a href={m.source_url} target="_blank" rel="noreferrer">
                source
              </a>
            </p>
            {!m.installed && (
              <code className="catalogue-download-hint">{m.download_hint}</code>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
