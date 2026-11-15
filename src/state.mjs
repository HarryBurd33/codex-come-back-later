/** Only account, host, thread identity and a marking generation are persistent. */
export function markerKey(identity) {
  const parts = [identity?.accountId, identity?.hostId, identity?.threadId];
  if (parts.some(part => typeof part !== 'string' || !part.length || part.length > 512)) {
    throw new TypeError('A stable account, host and thread are required');
  }
  return JSON.stringify(parts);
}

export function isAccepted(result) {
  return result?.status === 'sent' ||
    (result?.status === 'queued' && result.serverAccepted === true);
}

export function transition(current, command) {
  if (command.type === 'mark') {
    if (typeof command.generation !== 'string' || !command.generation.length) {
      throw new TypeError('A new marking generation is required');
    }
    if (command.generation === current?.generation) throw new TypeError('Generation must be new');
    return {generation: command.generation};
  }
  if (command.type === 'unmark') return null;
  if (command.type === 'accepted') {
    if (isAccepted(command.result) && command.generation != null &&
        current?.generation === command.generation) return null;
  }
  return current;
}
