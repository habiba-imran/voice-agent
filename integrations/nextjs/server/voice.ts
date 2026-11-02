import { createHmac } from 'node:crypto';
import { getVoiceIdentity } from './auth.ts';

const headers = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' };
function failure(status: number) { return new Response(JSON.stringify({ error: 'voice_unavailable' }), { status, headers }); }

async function boundedJson(body: ReadableStream<Uint8Array> | null, limit: number): Promise<unknown> {
  const reader = body?.getReader();
  if (!reader) return undefined;
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > limit) { await reader.cancel(); return undefined; }
      chunks.push(chunk.value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  } finally { reader.releaseLock(); }
}

/** Server route only. None of these variables may use the NEXT_PUBLIC_ prefix. */
type Services = {
  identity: typeof getVoiceIdentity;
  request: typeof fetch;
  environ: Record<string, string | undefined>;
};
export async function proxyVoice(request: Request, sessionId?: string,
  services: Services = { identity: getVoiceIdentity, request: fetch, environ: process.env }): Promise<Response> {
  try {
    const origin = services.environ.VOICE_WEB_ORIGIN;
    const secret = services.environ.VOICE_GATEWAY_ASSERTION_SECRET;
    const base = services.environ.VOICE_GATEWAY_URL;
    if (!origin || !secret || secret.length < 32 || !base) return failure(503);
    const target = new URL(base);
    if (target.protocol !== 'https:' || target.username || target.password || target.search || target.hash) return failure(503);
    if (request.headers.get('Origin') !== origin || request.headers.get('Content-Type')?.split(';')[0] !== 'application/json') return failure(403);
    const input = await boundedJson(request.body, 1024);
    if (input === null || typeof input !== 'object' || Array.isArray(input) || Object.keys(input).length !== 0) return failure(400);
    if (sessionId && !/^[a-f0-9]{32}$/.test(sessionId)) return failure(400);
    // Your adapter verifies an actual session/challenge; clients cannot supply these claims.
    const identity = await services.identity(request);
    if (!identity.subject || !identity.network) return failure(401);
    const now = Math.floor(Date.now() / 1000);
    const encode = (value: unknown) => Buffer.from(JSON.stringify(value)).toString('base64url');
    const body = `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({
      iss: 'voice-web', aud: 'voice-gateway', sub: identity.subject, network: identity.network,
      iat: now, nbf: now, exp: now + 60,
    })}`;
    const signature = createHmac('sha256', secret).update(body).digest('base64url');
    const path = sessionId ? `/v1/sessions/${sessionId}/end` : '/v1/sessions';
    const response = await services.request(new URL(path, base), {
      method: 'POST', cache: 'no-store', headers: {
        'Content-Type': 'application/json', Origin: origin, Authorization: `Bearer ${body}.${signature}`,
      }, body: '{}', signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) return failure(response.status === 429 ? 429 : 503);
    const raw = await boundedJson(response.body, 16384);
    if (raw === null || typeof raw !== 'object') return failure(503);
    const data = raw as Record<string, unknown>;
    let safe: Record<string, unknown>;
    if (sessionId) {
      if (typeof data.ended !== 'boolean') return failure(503);
      safe = { ended: data.ended };
    } else {
      if (typeof data.sessionId !== 'string' || !/^[a-f0-9]{32}$/.test(data.sessionId) ||
          typeof data.serverUrl !== 'string' || typeof data.token !== 'string' || data.token.length > 8192 ||
          typeof data.expiresAt !== 'number' || typeof data.deadline !== 'number') return failure(503);
      safe = { sessionId: data.sessionId, serverUrl: data.serverUrl, token: data.token,
        expiresAt: data.expiresAt, deadline: data.deadline };
    }
    return new Response(JSON.stringify(safe), { status: response.status, headers });
  } catch { return failure(503); } // Never return upstream exceptions, assertions, URLs or keys.
}
