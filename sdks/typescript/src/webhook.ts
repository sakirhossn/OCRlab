import * as crypto from 'crypto';

export function verifyWebhookSignature(
  secret: string,
  signatureHeader: string,
  timestampHeader: string,
  rawPayload: string | Buffer,
  toleranceSeconds = 300
): boolean {
  if (!signatureHeader || !timestampHeader) return false;

  const timestamp = parseInt(timestampHeader, 10);
  if (isNaN(timestamp)) return false;

  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - timestamp) > toleranceSeconds) {
    return false; // Replay prevention
  }

  const parts = signatureHeader.split(',');
  let receivedHash = '';
  for (const part of parts) {
    if (part.startsWith('v1=')) {
      receivedHash = part.slice(3);
      break;
    }
  }
  if (!receivedHash) return false;

  const dataToSign = `t=${timestamp}.` + (typeof rawPayload === 'string' ? rawPayload : rawPayload.toString('utf-8'));
  const expectedHash = crypto
    .createHmac('sha256', secret)
    .update(dataToSign)
    .digest('hex');

  return crypto.timingSafeEqual(
    Buffer.from(expectedHash, 'hex'),
    Buffer.from(receivedHash, 'hex')
  );
}
