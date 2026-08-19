import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "./useAuth";

/**
 * Connects to /api/sse/events while authenticated and invalidates the
 * affected React Query caches when the backend publishes events:
 *   job.state / job.progress / job.completed → jobs + dashboard
 *   inbox.updated                          → inbox + stats + dashboard
 * EventSource reconnects automatically on drop.
 */
export function useSse(): void {
  const { isAuthenticated, orgId } = useAuth();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!isAuthenticated || !orgId) return;

    const es = new EventSource("/api/sse/events", { withCredentials: true });

    const handleEvent = (event: MessageEvent) => {
      let payload: Record<string, unknown> = {};
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }
      const evName = event.type;
      if (evName.startsWith("job.")) {
        const jobId = typeof payload.job_id === "string" ? payload.job_id : null;
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
        if (jobId) {
          queryClient.invalidateQueries({ queryKey: ["job", jobId] });
        }
        queryClient.invalidateQueries({ queryKey: ["dashboard"] });
        if (evName === "job.completed") {
          queryClient.invalidateQueries({ queryKey: ["conversations"] });
          queryClient.invalidateQueries({ queryKey: ["pages"] });
        }
      } else if (evName === "inbox.updated") {
        queryClient.invalidateQueries({ queryKey: ["inbox"] });
        queryClient.invalidateQueries({ queryKey: ["inbox-stats"] });
        queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      } else if (evName === "conversation.updated") {
        queryClient.invalidateQueries({ queryKey: ["conversations"] });
        queryClient.invalidateQueries({ queryKey: ["inbox"] });
        queryClient.invalidateQueries({ queryKey: ["inbox-stats"] });
      }
    };

    const onMessage = (e: MessageEvent) => handleEvent(e);

    es.addEventListener("job.state", onMessage);
    es.addEventListener("job.progress", onMessage);
    es.addEventListener("job.completed", onMessage);
    es.addEventListener("inbox.updated", onMessage);
    es.addEventListener("conversation.updated", onMessage);

    return () => {
      es.removeEventListener("job.state", onMessage);
      es.removeEventListener("job.progress", onMessage);
      es.removeEventListener("job.completed", onMessage);
      es.removeEventListener("inbox.updated", onMessage);
      es.removeEventListener("conversation.updated", onMessage);
      es.close();
    };
  }, [isAuthenticated, orgId, queryClient]);
}
