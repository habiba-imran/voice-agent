import { proxyVoice } from '../../../../../../server/voice.ts';
export const runtime = 'nodejs';
export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  return proxyVoice(request, (await context.params).id);
}
