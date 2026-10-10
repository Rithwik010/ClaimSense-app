import { Navigate, Route, Routes } from "react-router";

import { Layout } from "./components/Layout";
import { EmptyState } from "./components/States";
import { ClaimDetail } from "./pages/ClaimDetail";
import { Claims } from "./pages/Claims";
import { Metrics } from "./pages/Metrics";
import { ReviewClaim } from "./pages/ReviewClaim";
import { ReviewQueue } from "./pages/ReviewQueue";
import { RuleOutcomes } from "./pages/RuleOutcomes";
import { SubmitClaim } from "./pages/SubmitClaim";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/submit" replace />} />
        <Route path="submit" element={<SubmitClaim />} />
        <Route path="queue" element={<ReviewQueue />} />
        <Route path="review/:claimId" element={<ReviewClaim />} />
        <Route path="claims" element={<Claims />} />
        <Route path="claims/:claimId" element={<ClaimDetail />} />
        <Route path="rule-outcomes" element={<RuleOutcomes />} />
        <Route path="metrics" element={<Metrics />} />
        <Route path="*" element={<EmptyState title="Page not found" />} />
      </Route>
    </Routes>
  );
}
