import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import test from 'node:test';
import { proxyVoice } from '../nextjs/server/voice.ts';
const environ = { VOICE_WEB_ORIGIN: 'https://example.invalid', VOICE_GATEWAY_URL: 'https://gateway.invalid',
  VOICE_GATEWAY_ASSERTION_SECRET: 'synthetic-assertion-secret-longer-than-32-characters' };
const make = (origin = environ.VOICE_WEB_ORIGIN, body = '{}') => new Request('https://example.invalid/api/voice/sessions', {
  method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json' }, body,
});

test('real server-side HMAC assertion is scoped and short, client cannot choose identity', async () => {
  const identity = async () => ({ subject: 'verified-user', network: 'verified-network' });
  let calls = 0;
  const request = (async (_input: RequestInfo | URL, init?: RequestInit) => {
    calls++;
    const signed = new Headers(init?.headers).get('Authorization')!.replace('Bearer ', '');
    const [header, claims, signature] = signed.split('.');
    assert.equal(signature, createHmac('sha256', environ.VOICE_GATEWAY_ASSERTION_SECRET).update(`${header}.${claims}`).digest('base64url'));
    const data = JSON.parse(Buffer.from(claims, 'base64url').toString());
    assert.equal(data.sub, 'verified-user'); assert.equal(data.aud, 'voice-gateway');
    assert.equal(data.exp - data.iat, 60);
    assert.equal(init?.body, '{}');
    return new Response(JSON.stringify({ token: 'synthetic-participant-token', sessionId: 'a'.repeat(32),
      serverUrl: 'wss://synthetic.livekit.cloud', expiresAt: Date.now()/1000+60,
      deadline: Date.now()/1000+300, private_debug: 'private-secret-must-not-escape' }), { status: 201 });
  }) as typeof fetch;
  const result = await proxyVoice(make(), undefined, { identity, request, environ });
  assert.equal(result.status, 201); assert.equal(calls, 1);
  assert.equal(result.headers.get('Cache-Control'), 'no-store');
  assert(!(await result.text()).includes('private_debug'));
});

for (const [label, input, id] of [
  ['origin', () => make('https://attacker.invalid'), undefined],
  ['oversize', () => make(environ.VOICE_WEB_ORIGIN, 'x'.repeat(2048)), undefined],
  ['injected fields', () => make(environ.VOICE_WEB_ORIGIN, '{"subject":"attacker"}'), undefined],
  ['path', () => make(), '../rooms/private'],
] as const) test(`rejects ${label} before upstream access`, async () => {
  let calls = 0;
  const request = (async () => { calls++; throw new Error('private'); }) as typeof fetch;
  const result = await proxyVoice(input(), id, { identity: async () => ({ subject: 'user', network: 'net' }), request, environ });
  assert(result.status >= 400); assert.equal(calls, 0);
  assert(!(await result.text()).includes('private'));
});

test('missing application auth fails closed; raw upstream failures do not escape', async () => {
  const request = (async () => new Response('private credential payload', { status: 500 })) as typeof fetch;
  const authFailure = await proxyVoice(make(), undefined, {
    identity: async () => { throw new Error('private'); }, request, environ,
  });
  assert.equal(authFailure.status, 503);
  const upstreamFailure = await proxyVoice(make(), undefined, {
    identity: async () => ({ subject: 'user', network: 'net' }), request, environ,
  });
  assert.equal(upstreamFailure.status, 503);
  assert(!(await upstreamFailure.text()).includes('private'));
});
