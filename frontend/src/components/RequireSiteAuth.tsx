/** Route guard for the site-wide login gate — redirects to /login when there's
 * no stored token. Doesn't validate the token itself (the backend does that on
 * every request); this just avoids flashing real pages before the first API
 * call redirects you anyway. */
import { Navigate, Outlet } from "react-router-dom";

export default function RequireSiteAuth() {
  const token = localStorage.getItem("access_token");
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
