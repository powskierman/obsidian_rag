export type DataServiceState = 'online' | 'empty' | 'offline';

export function getVectorServiceState(documentCount: number): DataServiceState {
  return documentCount > 0 ? 'online' : 'empty';
}

export function getKnowledgeGraphServiceState(
  graph: { nodes?: number; edges?: number; graph_loaded?: boolean } | null | undefined
): DataServiceState {
  if (!graph) {
    return 'offline';
  }

  const nodes = graph.nodes ?? 0;
  const edges = graph.edges ?? 0;

  if (nodes > 0 || edges > 0) {
    return 'online';
  }

  return 'empty';
}

export function getLightRAGServiceState(
  lightrag: { nodes?: number } | null | undefined
): DataServiceState {
  if (!lightrag) {
    return 'offline';
  }

  return (lightrag.nodes ?? 0) > 0 ? 'online' : 'empty';
}

export function getServiceTone(status: DataServiceState): {
  dotClass: string;
  textClass: string;
  badgeClass: string;
  label: string;
} {
  switch (status) {
    case 'online':
      return {
        dotClass: 'bg-green-500',
        textClass: 'text-green-500',
        badgeClass: 'bg-green-500/10 text-green-500',
        label: 'Online',
      };
    case 'empty':
      return {
        dotClass: 'bg-amber-400',
        textClass: 'text-amber-400',
        badgeClass: 'bg-amber-400/10 text-amber-300',
        label: 'Empty',
      };
    default:
      return {
        dotClass: 'bg-red-500',
        textClass: 'text-red-500',
        badgeClass: 'bg-red-500/10 text-red-500',
        label: 'Offline',
      };
  }
}
