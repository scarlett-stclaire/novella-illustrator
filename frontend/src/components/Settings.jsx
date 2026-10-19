import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Settings() {
  const [providers, setProviders] = useState([]);
  const [defaultProviderId, setDefaultProviderId] = useState("ollama");
  const [keyInputs, setKeyInputs] = useState({});
  const [busyProvider, setBusyProvider] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  async function refresh() {
    const data = await api.listTextProviders();
    setProviders(data.providers);
    setDefaultProviderId(data.default_provider_id);
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
    </div>
  );
}
