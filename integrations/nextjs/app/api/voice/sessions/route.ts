import { proxyVoice } from '../../../../server/voice.ts';
export const runtime = 'nodejs';
export async function POST(request: Request) { return proxyVoice(request); }
