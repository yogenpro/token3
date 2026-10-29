/** Compare asset-relative paths while exercising the actual production prefix. */
export function sitePathname(url: string): string {
  const base = process.env.TOKEN3_TEST_BASE_PATH ?? '/';
  const pathname = new URL(url).pathname;
  return pathname.startsWith(base) ? `/${pathname.slice(base.length)}` : pathname;
}
