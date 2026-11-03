import { StatusPage } from "@/components/layout/StatusPage";

export default function NotFound() {
  return <StatusPage code="404" title="We could not find that page" body="The link may be old, or the listing may have been removed." />;
}
