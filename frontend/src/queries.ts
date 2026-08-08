import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getCosts, getRequest, getRequests } from "./api";
import type { GetRequestsParams } from "./api";

export function useRequestsQuery(params: GetRequestsParams) {
  return useQuery({
    queryKey: ["requests", params.page, params.model, params.status],
    queryFn: () => getRequests(params),
    placeholderData: keepPreviousData,
  });
}

export function useRequestQuery(id: string) {
  return useQuery({
    queryKey: ["request", id],
    queryFn: () => getRequest(id),
  });
}

export function useCostsQuery() {
  return useQuery({
    queryKey: ["costs"],
    queryFn: getCosts,
  });
}
