/** Replace ONLY this adapter with your application-owned, server-verified authentication.
 * Anonymous sites need verified abuse/challenge protection and a stable server-owned identity.
 * Never trust a body/cookie/header value as an authenticated subject or a raw forwarded IP.
 */
export async function getVoiceIdentity(_request: Request): Promise<{ subject: string; network: string }> {
  throw new Error('Voice authentication adapter is not configured'); // Fail closed.
}
