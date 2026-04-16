type TopicListener = (topic: string) => void;

const listeners = new Set<TopicListener>();

export function subscribeTopics(fn: TopicListener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function emitTopic(topic: string): void {
  for (const fn of listeners) fn(topic);
}
