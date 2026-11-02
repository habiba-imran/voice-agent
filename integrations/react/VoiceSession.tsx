'use client';

import { useEffect, useRef, useState } from 'react';
import { ParticipantKind, Room, RoomEvent, Track } from 'livekit-client';
import { VoiceConnection, type VoiceRoom, type VoiceState } from './session.ts';

/** No portfolio content or styling. Mount inside any React/Next.js application. */
export function VoiceSession() {
  const [state, setState] = useState<VoiceState>('idle');
  const [message, setMessage] = useState('');
  const [muted, setMuted] = useState(false);
  const output = useRef<HTMLDivElement>(null);
  const connection = useRef<VoiceConnection | null>(null);
  useEffect(() => {
    const makeRoom = (): VoiceRoom => {
      const room = new Room();
      const elements = new Set<HTMLMediaElement>();
      room.on(RoomEvent.TrackSubscribed, track => {
        if (track.kind === Track.Kind.Audio) {
          const element = track.attach();
          elements.add(element); output.current?.appendChild(element);
        }
      });
      room.on(RoomEvent.TrackUnsubscribed, track => {
        track.detach().forEach(element => { element.remove(); elements.delete(element); });
      });
      return {
        connect: (url, token) => room.connect(url, token),
        microphone: async enabled => { await room.localParticipant.setMicrophoneEnabled(enabled); },
        startAudio: () => room.startAudio(),
        disconnect: async () => {
          await room.disconnect(true);
          elements.forEach(element => element.remove()); elements.clear();
        },
        onDisconnected: callback => { room.on(RoomEvent.Disconnected, callback); },
        onReconnecting: callback => { room.on(RoomEvent.Reconnecting, callback); },
        onReconnected: callback => { room.on(RoomEvent.Reconnected, callback); },
        onAgentLeft: callback => { room.on(RoomEvent.ParticipantDisconnected, participant => {
          if (participant.kind === ParticipantKind.AGENT) callback();
        }); },
      };
    };
    const current = new VoiceConnection(makeRoom, (next, text) => {
      setState(next); setMessage(text ?? '');
      if (next === 'starting') setMuted(false);
    });
    connection.current = current;
    return () => { connection.current = null; void current.dispose(); };
  }, []);
  const active = ['starting', 'connecting', 'connected', 'reconnecting', 'ending'].includes(state);
  return <section aria-label="Voice conversation">
    <p role="status">{state}{message ? `: ${message}` : ''}</p>
    <button disabled={active} onClick={() => void connection.current?.start()}>Start voice</button>
    <button disabled={state !== 'connected'} onClick={() => {
      setMuted(!muted); void connection.current?.mute(!muted);
    }}>{muted ? 'Unmute' : 'Mute'}</button>
    <button disabled={!active} onClick={() => void connection.current?.stop()}>End voice</button>
    <button disabled={state !== 'connected'} onClick={() => {
      void connection.current?.enableAudio().catch(() => setMessage('Allow audio playback in your browser.'));
    }}>Enable audio</button>
    <div ref={output} />
  </section>;
}
