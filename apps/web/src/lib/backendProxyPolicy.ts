export function allowedBackendPath(path: readonly string[]): boolean {
  if (path.length === 1 && path[0] === "health") return true;
  return path[0] === "api" && path.at(-1) !== "process" &&
    path.every((part) => /^[a-zA-Z0-9_-]+$/.test(part));
}

export function configuredBackend(value: string): URL | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.pathname === "/" && !url.search && !url.hash && !url.username && !url.password ? url : null;
  } catch {
    return null;
  }
}

export function trustedWriteOrigin(origin: string | null, configured: string): boolean {
  return origin !== null && origin === configured;
}

export async function boundedBody(request: Request, limit: number): Promise<Uint8Array<ArrayBuffer> | null> {
  if (Number(request.headers.get("content-length") ?? "0") > limit) return null;
  const chunks: Uint8Array[] = [];
  let size = 0;
  if (request.body) {
    const reader = request.body.getReader();
    while (true) {
      const item = await reader.read();
      if (item.done) break;
      size += item.value.byteLength;
      if (size > limit) {
        await reader.cancel();
        return null;
      }
      chunks.push(item.value);
    }
  }
  return new Uint8Array(Buffer.concat(chunks));
}
