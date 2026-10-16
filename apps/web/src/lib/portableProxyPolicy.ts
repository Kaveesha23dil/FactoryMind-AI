export function sessionCookie(header: string | null): string | null {
  const value = header?.split(";").map(part => part.trim()).find(part => part.startsWith("fm_session="))?.slice(11);
  return value && /^[A-Za-z0-9_.-]{20,16000}$/.test(value) ? value : null;
}
export function portableAuthorization(header: string | null): string | null {
  const token = sessionCookie(header);
  return token ? `Bearer ${token}` : null;
}
