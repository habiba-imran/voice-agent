import assert from 'node:assert/strict';
import test from 'node:test';
import { VoiceConnection, type VoiceRoom, type VoiceState } from '../react/session.ts';

function room() {
  const events: Record<string, () => void> = {};
  const seen = { connects: 0, disconnects: 0, microphone: [] as boolean[] };
  const adapter: VoiceRoom = {
    connect: async () => { seen.connects++; }, disconnect: async () => { seen.disconnects++; },
    microphone: async enabled => { seen.microphone.push(enabled); }, startAudio: async () => {},
    onDisconnected: fn => { events.disconnect = fn; }, onReconnecting: fn => { events.reconnect = fn; },
    onReconnected: fn => { events.connected = fn; }, onAgentLeft: fn => { events.agentLeft = fn; },
  };
  return { adapter, events, seen };
}
const grant = () => ({ sessionId: 'a'.repeat(32), serverUrl: 'wss://synthetic.livekit.cloud',
  token: 'synthetic-scoped-token', deadline: Date.now() / 1000 + 300, expiresAt: Date.now() / 1000 + 60 });
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });

test('start/mute/reconnect/end do not issue duplicate participant tokens', async () => {
  const fake = room(), states: VoiceState[] = [], calls: string[] = [];
  const request = (async (input: RequestInfo | URL) => { calls.push(String(input));
    return String(input).endsWith('/end') ? response({ ended: true }) : response(grant(), 201);
  }) as typeof fetch;
  const connection = new VoiceConnection(() => fake.adapter, state => states.push(state), request);
  await Promise.all([connection.start(), connection.start()]);
  assert.equal(fake.seen.connects, 1);
  await connection.mute(true); await connection.mute(false);
  fake.events.reconnect(); fake.events.connected();
  assert.equal(calls.length, 1);
  await connection.stop(); await connection.dispose();
  assert.equal(calls.length, 2);
  assert.deepEqual(fake.seen.microphone, [true, false, true]);
  assert(states.includes('reconnecting'));
});

test('stop before token arrives cleans late reservation without connecting', async () => {
  const fake = room();
  let release!: (value: Response) => void;
  let ends = 0;
  const request = (async (input: RequestInfo | URL) => {
    if (String(input).endsWith('/end')) { ends++; return response({ ended: true }); }
    return new Promise<Response>(resolve => { release = resolve; });
  }) as typeof fetch;
  const connection = new VoiceConnection(() => fake.adapter, () => {}, request);
  const starting = connection.start();
  await Promise.resolve();
  await connection.stop();
  release(response(grant(), 201)); await starting;
  assert.equal(fake.seen.connects, 0); assert.equal(ends, 1);
  await connection.dispose();
});

test('unmount during room connection cannot leave the microphone running', async () => {
  const fake = room();
  let connected!: () => void;
  fake.adapter.connect = () => new Promise<void>(resolve => { connected = resolve; });
  const request = (async (input: RequestInfo | URL) => String(input).endsWith('/end')
    ? response({ ended: true }) : response(grant(), 201)) as typeof fetch;
  const connection = new VoiceConnection(() => fake.adapter, () => {}, request);
  const starting = connection.start();
  while (!connected) await new Promise(resolve => setTimeout(resolve, 1));
  await connection.dispose(); connected(); await starting;
  assert.deepEqual(fake.seen.microphone, []);
  assert(fake.seen.disconnects >= 1);
});

test('pending server cleanup is reported honestly and tokens/errors are never logged', async () => {
  const fake = room(), messages: string[] = [];
  const request = (async (input: RequestInfo | URL) => String(input).endsWith('/end')
    ? response({ ended: false }, 202) : response(grant(), 201)) as typeof fetch;
  const connection = new VoiceConnection(() => fake.adapter, (_state, message) => { if (message) messages.push(message); }, request);
  await connection.start(); await connection.stop();
  assert(messages.some(message => message.includes('cleanup is pending')));
  assert(!messages.join().includes('synthetic-scoped-token'));
  await connection.dispose();
});

test('quota failure never creates a connection or echoes an upstream payload', async () => {
  const fake = room(), messages: string[] = [];
  const request = (async () => response({ error: 'private-provider-payload' }, 429)) as typeof fetch;
  const connection = new VoiceConnection(() => fake.adapter, (_state, message) => { if (message) messages.push(message); }, request);
  await connection.start(); await connection.dispose();
  assert.equal(fake.seen.connects, 0);
  assert(messages.some(message => message.includes('Session limit')));
  assert(!messages.join().includes('private'));
});

test('unsupported browser and repeated end actions do not leak resources', async () => {
  const states: VoiceState[] = [];
  const failed = new VoiceConnection(() => { throw new Error('private'); }, state => states.push(state));
  await failed.start(); await failed.dispose();
  assert(states.includes('error'));
  const fake = room();
  let ends = 0;
  const request = (async (input: RequestInfo | URL) => {
    if (String(input).endsWith('/end')) { ends++; return response({ ended: true }); }
    return response(grant(), 201);
  }) as typeof fetch;
  const connection = new VoiceConnection(() => fake.adapter, () => {}, request);
  await connection.start();
  await Promise.all([connection.stop(), connection.stop(), connection.stop()]);
  assert.equal(ends, 1);
  await connection.dispose();
});
