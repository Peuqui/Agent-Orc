/** Whether an API answer came from the login page of a reverse proxy instead of from the app.
 *
 * Behind a proxy with a login of its own (narnia: Authelia) a request without a valid proxy session
 * is redirected to the proxy's login page. fetch follows that redirect silently and hands back the
 * page's HTML instead of the API's JSON — with status 200, so nothing else would notice. */
export function answeredByProxyLogin(redirected: boolean, contentType: string | null): boolean {
  return redirected && (contentType ?? '').includes('text/html')
}
