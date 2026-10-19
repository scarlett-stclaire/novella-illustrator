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

  async function refresh() {
    const [providersData, catalogueData] = await Promise.all([
      api.listTextProviders(),
      api.listCatalogue(),
    ]);
    setProviders(providersData.providers);
    setDefaultProviderId(providersData.default_provider_id);
    setCatalogue(catalogueData.models);
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
