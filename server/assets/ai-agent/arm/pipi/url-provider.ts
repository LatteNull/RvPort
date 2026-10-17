/**
 * url-provider.ts — pi extension
 *
 * Registers an in-memory provider ("cli-url") from PI_BASE_* environment
 * variables. Designed to be driven by the `pipi` wrapper script.
 *
 * Behaviour:
 *   - When PI_BASE_URL is unset  →  no-op (normal `pi` usage is unaffected).
 *   - When PI_BASE_URL is set     →  registers a single model under provider
 *                                   "cli-url". Nothing is written to disk;
 *                                   the registration lives only in this
 *                                   pi process.
 *
 * Install location (auto-discovered by pi, no -e needed):
 *   ~/.pi/agent/extensions/url-provider.ts
 *
 * Field reference (verified against pi's ProviderConfigInput type and
 * provider-composer.js):
 *   id            required              model id sent to API
 *   name          default = id          display name in /model
 *   api           default openai-completions
 *   baseUrl       required (provider-level here)
 *   reasoning     default false
 *   input         default ["text"]      use ["text","image"] with --image
 *   contextWindow default 128000
 *   maxTokens     default 16384
 *   cost          default all-zero      for usage tracking only
 *   thinkingLevelMap / samplingParams / compat / headers
 *                 optional              advanced, set via --model-json
 */

const DEFAULT_API = "openai-completions";
const DEFAULT_CONTEXT = 128000;
const DEFAULT_MAX_TOKENS = 16384;

function log(msg: string): void {
  // Visible in `pi --verbose` startup output.
  console.error(`[url-provider] ${msg}`);
}

type RegisterFn = (name: string, config: Record<string, unknown>) => void;

export default function (pi: { registerProvider: RegisterFn }): void {
  const baseUrl = process.env.PI_BASE_URL;
  if (!baseUrl) {
    // No-op: not launched via pipi wrapper. Keeps normal pi usage clean.
    return;
  }

  const modelId = process.env.PI_BASE_MODEL_ID;
  if (!modelId) {
    log("PI_BASE_URL set but PI_BASE_MODEL_ID missing — skipping registration");
    return;
  }

  const api = process.env.PI_BASE_API || DEFAULT_API;
  const modelName = process.env.PI_BASE_MODEL_NAME || modelId;
  const reasoning = process.env.PI_BASE_REASONING === "1";
  const image = process.env.PI_BASE_IMAGE === "1";
  const apiKey = process.env.PI_BASE_API_KEY || "";

  const contextWindow = Number(process.env.PI_BASE_CONTEXT ?? DEFAULT_CONTEXT);
  const maxTokens = Number(process.env.PI_BASE_MAX_TOKENS ?? DEFAULT_MAX_TOKENS);

  if (!Number.isFinite(contextWindow) || contextWindow <= 0) {
    log(
      `ERROR: invalid contextWindow ${process.env.PI_BASE_CONTEXT} — skipping registration`,
    );
    return;
  }
  if (!Number.isFinite(maxTokens) || maxTokens <= 0) {
    log(
      `ERROR: invalid maxTokens ${process.env.PI_BASE_MAX_TOKENS} — skipping registration`,
    );
    return;
  }

  if (!apiKey) {
    log(
      "WARNING: PI_BASE_API_KEY is empty — model will be registered but " +
        "hidden in /model and --list-models until auth is provided",
    );
  }

  // Base model definition. Cost is zero by default (self-hosted / internal).
  const model: Record<string, unknown> = {
    id: modelId,
    name: modelName,
    reasoning,
    input: image ? ["text", "image"] : ["text"],
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    contextWindow,
    maxTokens,
  };

  // Advanced override: --model-json blob (compat / thinkingLevelMap /
  // samplingParams / cost / custom headers / etc.). Keys here win.
  const jsonBlob = process.env.PI_BASE_MODEL_JSON;
  if (jsonBlob) {
    try {
      const overrides = JSON.parse(jsonBlob);
      if (overrides && typeof overrides === "object" && !Array.isArray(overrides)) {
        Object.assign(model, overrides);
      } else {
        log("ERROR: PI_BASE_MODEL_JSON must be a JSON object — skipping registration");
        return;
      }
    } catch (e) {
      log(
        `ERROR: failed to parse PI_BASE_MODEL_JSON: ${
          e instanceof Error ? e.message : e
        } — skipping registration`,
      );
      return;
    }
  }

  pi.registerProvider("cli-url", {
    baseUrl,
    api,
    // Let pi's own resolver handle env interpolation / !command syntax.
    // A resolved non-empty value is what makes the model visible in /model.
    apiKey: "$PI_BASE_API_KEY",
    models: [model],
  });

  log(
    `registered cli-url/${model.id} ctx=${model.contextWindow} ` +
      `max=${model.maxTokens} api=${api} reasoning=${model.reasoning} ` +
      `input=${(model.input as string[]).join(",")}`,
  );
}
