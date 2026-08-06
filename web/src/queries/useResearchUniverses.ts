import { useQuery } from "@tanstack/react-query";
import {
  type CollectionType,
  fetchResearchUniverse,
  fetchResearchUniverseIssuers,
  fetchResearchUniverses,
} from "../api/researchUniverse";

export function useResearchUniverses(collectionType?: CollectionType) {
  return useQuery({
    queryKey: ["research-universes", collectionType],
    queryFn: () => fetchResearchUniverses(collectionType),
  });
}

export function useResearchUniverse(universeId: string | undefined) {
  return useQuery({
    queryKey: ["research-universe", universeId],
    queryFn: () => fetchResearchUniverse(universeId as string),
    enabled: universeId !== undefined,
  });
}

export function useResearchUniverseIssuers(universeId: string | undefined) {
  return useQuery({
    queryKey: ["research-universe-issuers", universeId],
    queryFn: () => fetchResearchUniverseIssuers(universeId as string),
    enabled: universeId !== undefined,
  });
}
