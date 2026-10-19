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

async function requestForm(path, formData) {
  const response = await fetch(`${BASE}${path}`, { method: "POST", body: formData });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `${response.status}: request failed`);
  }
  return response.json();
}

export const api = {
  health: () => request("/health"),
  extractPdf: (file) => {
    const formData = new FormData();
    formData.append("file", file);
    return requestForm("/ingest/pdf", formData);
  },
  extractUrls: (urls) =>
    request("/ingest/urls", { method: "POST", body: JSON.stringify({ urls }) }),
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
  extractCharacters: (novellaId, textProviderId) =>
    request(
      `/novellas/${novellaId}/characters/extract${
        textProviderId
          ? `?text_provider_id=${encodeURIComponent(textProviderId)}`
          : ""
      }`,
      { method: "POST" }
    ),
  addCharacter: (novellaId, { name, synopsis, visualDescription }) =>
    request(`/novellas/${novellaId}/characters`, {
      method: "POST",
      body: JSON.stringify({
        name,
        synopsis: synopsis || "",
        visual_description: visualDescription || "",
      }),
    }),
  updateCharacter: (novellaId, characterId, fields) =>
    request(`/novellas/${novellaId}/characters/${characterId}`, {
      method: "PATCH",
      body: JSON.stringify({
        name: fields.name,
        synopsis: fields.synopsis,
        visual_description: fields.visualDescription,
      }),
    }),
  deleteCharacter: (novellaId, characterId) =>
    request(`/novellas/${novellaId}/characters/${characterId}`, {
      method: "DELETE",
    }),
  uploadCharacterImage: (novellaId, characterId, file) => {
    const formData = new FormData();
    formData.append("file", file);
    return requestForm(
      `/novellas/${novellaId}/characters/${characterId}/image/upload`,
      formData
    );
  },
  generateCharacterImage: (novellaId, characterId, engineId) =>
    request(
      `/novellas/${novellaId}/characters/${characterId}/image/generate${
        engineId ? `?engine_id=${encodeURIComponent(engineId)}` : ""
      }`,
      { method: "POST" }
    ),
  applyCharactersToScenes: (novellaId) =>
    request(`/novellas/${novellaId}/characters/apply-to-scenes`, {
      method: "POST",
    }),
  updateScene: (novellaId, sceneId, { summary, imagePrompt }) =>
    request(`/novellas/${novellaId}/scenes/${sceneId}`, {
      method: "PATCH",
      body: JSON.stringify({ summary, image_prompt: imagePrompt }),
    }),
  moveScene: (novellaId, sceneId, direction) =>
    request(`/novellas/${novellaId}/scenes/${sceneId}/move?direction=${direction}`, {
      method: "POST",
    }),
  mergeSceneNext: (novellaId, sceneId) =>
    request(`/novellas/${novellaId}/scenes/${sceneId}/merge-next`, {
      method: "POST",
    }),
  splitScene: (novellaId, sceneId, { summaryA, promptA, summaryB, promptB }) =>
    request(`/novellas/${novellaId}/scenes/${sceneId}/split`, {
      method: "POST",
      body: JSON.stringify({
        summary_a: summaryA,
        image_prompt_a: promptA,
        summary_b: summaryB,
        image_prompt_b: promptB,
      }),
    }),
};
