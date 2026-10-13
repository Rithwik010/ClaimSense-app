// Routes (D-AUTH-1): the login page is public; every other page needs a logged-in user, and each
// is for some roles only (another role's URL shows "You don't have access"). "/" goes to the
// role's home: provider My claims, reviewer Review queue, admin Overview.

import { Route, Routes } from "react-router";

import { Allow, Home, RequireLogin } from "./components/Guards";
import { Layout } from "./components/Layout";
import { EmptyState } from "./components/States";
import { AuditLookup } from "./pages/AuditLookup";
import { ClaimDetail } from "./pages/ClaimDetail";
import { ClaimResult } from "./pages/ClaimResult";
import { Claims } from "./pages/Claims";
import { Login } from "./pages/Login";
import { Metrics } from "./pages/Metrics";
import { MyClaims } from "./pages/MyClaims";
import { Overview } from "./pages/Overview";
import { ReviewClaim } from "./pages/ReviewClaim";
import { Returned } from "./pages/Returned";
import { ReviewQueue } from "./pages/ReviewQueue";
import { SubmitClaim } from "./pages/SubmitClaim";
import { SystemStatus } from "./pages/SystemStatus";

export function App() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route element={<RequireLogin />}>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route element={<Allow roles={["provider"]} />}>
            <Route path="my-claims" element={<MyClaims />} />
            <Route path="my-claims/:claimId" element={<ClaimResult />} />
            <Route path="submit" element={<SubmitClaim />} />
          </Route>
          <Route element={<Allow roles={["reviewer"]} />}>
            <Route path="review/:claimId" element={<ReviewClaim />} />
          </Route>
          <Route element={<Allow roles={["reviewer", "admin"]} />}>
            <Route path="queue" element={<ReviewQueue />} />
            <Route path="claims" element={<Claims />} />
            <Route path="claims/:claimId" element={<ClaimDetail />} />
            <Route path="rule-outcomes" element={<Returned />} />
          </Route>
          <Route element={<Allow roles={["admin"]} />}>
            <Route path="overview" element={<Overview />} />
            <Route path="metrics" element={<Metrics />} />
            <Route path="audit" element={<AuditLookup />} />
            <Route path="system" element={<SystemStatus />} />
          </Route>
          <Route path="*" element={<EmptyState title="Page not found" />} />
        </Route>
      </Route>
    </Routes>
  );
}
