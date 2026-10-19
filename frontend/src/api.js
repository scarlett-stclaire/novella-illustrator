const BASE = "/api";

async function request(path, options) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text}`);
  }
  return response.json();
}

export const api = {
  health: () => request("/health"),
  listNovellas: () => request("/novellas"),
  createNovella: (title, text, targetSceneCount) =>
    request("/novellas", {
      method: "POST",
      body: JSON.stringify({
        title,
        text,
        target_scene_count: targetSceneCount || null,
      }),
    }),
  getNovella: (id) => request(`/novellas/${id}`),
  breakdown: (id, textProviderId) =>
    request(
      `/novellas/${id}/breakdown${
        textProviderId
          ? `?text_provider_id=${encodeURIComponent(textProviderId)}`
          : ""
      }`,
      { method: "POST" }
    ),
  updateScenePrompt: (novellaId, sceneId, imagePrompt) =>
    request(`/novellas/${novellaId}/scenes/${sceneId}`, {
      method: "PATCH",
      body: JSON.stringify({ image_prompt: imagePrompt }),
    }),
  listEngines: () => request("/engines"),
  generateSceneImage: (novellaId, sceneId, engineId) =>
    request(
      `/novellas/${novellaId}/scenes/${sceneId}/generate${
        engineId ? `?engine_id=${encodeURIComponent(engineId)}` : ""
      }`,
      { method: "POST" }
    ),
  regenerateSceneImage: (novellaId, sceneId, feedback, engineId) =>
    request(`/novellas/${novellaId}/scenes/${sceneId}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ feedback, engine_id: engineId || null }),
    }),
  addScene: (novellaId, { summary, imagePrompt, afterSceneId }) =>
    request(`/novellas/${novellaId}/scenes`, {
      method: "POST",
      body: JSON.stringify({
        summary,
        image_prompt: imagePrompt,
        after_scene_id: afterSceneId || null,
      }),
    }),
  deleteScene: (novellaId, sceneId) =>
    request(`/novellas/${novellaId}/scenes/${sceneId}`, { method: "DELETE" }),
  listTextProviders: () => request("/settings/providers"),
  listCatalogue: () => request("/settings/catalogue"),
  getNovellaCostPerf: (novellaId) => request(`/novellas/${novellaId}/cost-perf`),
  recommendForScene: (novellaId, sceneId, feedback) =>
    request(
      `/novellas/${novellaId}/scenes/${sceneId}/recommend${
        feedback ? `?feedback=${encodeURIComponent(feedback)}` : ""
      }`
    ),
  saveProviderKey: (providerId, apiKey) =>
    request(`/settings/providers/${providerId}/key`, {
      method: "POST",
      body: JSON.stringify({ api_key: apiKey }),
    }),
  deleteProviderKey: (providerId) =>
    request(`/settings/providers/${providerId}/key`, { method: "DELETE" }),
  setDefaultProvider: (providerId) =>
    request("/settings/default-provider", {
      method: "POST",
      body: JSON.stringify({ provider_id: providerId || null }),
    }),
};
