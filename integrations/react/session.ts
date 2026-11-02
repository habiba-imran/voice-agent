/** Framework-neutral browser lifecycle. Tokens stay in memory; limits are server-owned. */
export type VoiceState = 'idle' | 'starting' | 'connecting' | 'connected' | 'reconnecting' | 'ending' | 'ended' | 'error';
export interface VoiceRoom {
  connect(url: string, token: string): Promise<void>;
  disconnect(): Promise<void>;
  microphone(enabled: boolean): Promise<void>;
  startAudio(): Promise<void>;
  onDisconnected(callback: () => void): void;
  onReconnecting(callback: () => void): void;
  onReconnected(callback: () => void): void;
  onAgentLeft(callback: () => void): void;
}
type Grant = { sessionId: string; serverUrl: string; token: string; deadline: number; expiresAt: number };

function grantFrom(value: unknown): Grant {
  const item = value as Partial<Grant>;
  if (!item || typeof item.sessionId !== 'string' || !/^[a-f0-9]{32}$/.test(item.sessionId) ||
      typeof item.token !== 'string' || item.token.length > 8192 || item.token.length < 1 ||
      typeof item.serverUrl !== 'string' || typeof item.deadline !== 'number' ||
      typeof item.expiresAt !== 'number' || !Number.isFinite(item.deadline) ||
      !Number.isFinite(item.expiresAt) ||
      item.deadline <= Date.now() / 1000 || item.expiresAt <= Date.now() / 1000) {
    throw new Error('invalid_grant');
  }
  const url = new URL(item.serverUrl);
  if (url.protocol !== 'wss:' || !url.hostname || url.username || url.password || url.search || url.hash) {
    throw new Error('invalid_grant');
  }
  return item as Grant;
}

export class VoiceConnection {
  private epoch = 0;
  private pending = false;
  private disposed = false;
  private room?: VoiceRoom;
  private grant?: Grant;
  private deadlineTimer?: ReturnType<typeof setTimeout>;
  private stopping?: Promise<void>;
  private makeRoom: () => VoiceRoom;
  private report: (state: VoiceState, message?: string) => void;
  private request: typeof fetch;
  private base: string;
  constructor(
    makeRoom: () => VoiceRoom,
    report: (state: VoiceState, message?: string) => void,
    request: typeof fetch = fetch,
    base = '/api/voice/sessions',
  ) { this.makeRoom = makeRoom; this.report = report; this.request = request; this.base = base; }

  private state(state: VoiceState, message?: string) {
    if (!this.disposed) this.report(state, message);
  }
  private async remoteEnd(id: string) {
    try {
      const response = await this.request(`${this.base}/${id}/end`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(12000),
      });
      return response.status === 200 && (await response.json()).ended === true;
    } catch { return false; } // Persistent gateway reaper remains authoritative.
  }

  async start() {
    if (this.pending || this.room || this.disposed || this.stopping) return;
    this.pending = true;
    const epoch = ++this.epoch;
    let room: VoiceRoom;
    try { room = this.makeRoom(); }
    catch {
      this.pending = false;
      this.state('error', 'Voice is not supported by this browser.');
      return;
    }
    this.room = room;
    this.state('starting');
    let issued: Grant | undefined;
    try {
      // User gesture initiates playback unlock. Permission may still need a later audio button.
      await room.startAudio();
      const response = await this.request(this.base, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(12000),
      });
      if (!response.ok) throw new Error(response.status === 429 ? 'limit_reached' : 'unavailable');
      issued = grantFrom(await response.json());
      if (epoch !== this.epoch || this.disposed) {
        await this.remoteEnd(issued.sessionId);
        await room.disconnect();
        return;
      }
      this.grant = issued;
      room.onDisconnected(() => { if (epoch === this.epoch) void this.stop(); });
      room.onAgentLeft(() => { if (epoch === this.epoch) void this.stop(); });
      room.onReconnecting(() => { if (epoch === this.epoch) this.state('reconnecting'); });
      room.onReconnected(() => { if (epoch === this.epoch) this.state('connected'); });
      this.state('connecting');
      await room.connect(issued.serverUrl, issued.token);
      if (epoch !== this.epoch || this.disposed) { await room.disconnect(); return; }
      await room.microphone(true);
      if (epoch !== this.epoch || this.disposed) { await room.disconnect(); return; }
      this.state('connected');
      this.deadlineTimer = setTimeout(() => void this.stop(), Math.max(0, issued.deadline * 1000 - Date.now()));
    } catch (error) {
      if (issued) await this.remoteEnd(issued.sessionId);
      await room.disconnect().catch(() => {});
      if (epoch === this.epoch) {
        this.room = undefined; this.grant = undefined;
        this.state('error', error instanceof Error && error.message === 'limit_reached'
          ? 'Session limit reached. Try again later.' : 'Unable to start voice. Check permissions and connection.');
      }
    } finally { this.pending = false; }
  }

  async mute(muted: boolean) {
    try { await this.room?.microphone(!muted); }
    catch { this.state('connected', 'Microphone could not be changed.'); }
  }
  async enableAudio() { await this.room?.startAudio(); }

  async stop() {
    if (this.stopping) return this.stopping;
    const operation = this.finishStop();
    this.stopping = operation;
    try { await operation; }
    finally { if (this.stopping === operation) this.stopping = undefined; }
  }
  private async finishStop() {
    ++this.epoch; // A late start result is cleaned up rather than adopted.
    clearTimeout(this.deadlineTimer);
    const room = this.room, grant = this.grant;
    this.room = undefined; this.grant = undefined;
    this.state('ending');
    await room?.disconnect().catch(() => {});
    const confirmed = !grant || await this.remoteEnd(grant.sessionId);
    this.state('ended', confirmed ? undefined : 'Disconnected locally; server cleanup is pending.');
  }
  async dispose() { this.disposed = true; await this.stop(); }
}
