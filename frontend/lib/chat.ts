import type { ChatMessage, ChatTraceItem } from "./api";

/**
 * Conversation bookkeeping, kept out of the component so it can be checked
 * directly.
 *
 * Both decisions here are invisible when they go wrong. A bad history still
 * produces an answer, just a worse one, and a stale reply still renders, just
 * under the wrong question.
 */

export type Turn = ChatMessage & {
  trace?: ChatTraceItem[];
  /** Set on bubbles the client produced itself, not the model. */
  failed?: boolean;
};

const ERROR_HINT = "Is Ollama running and the model pulled?";

/** The bubble shown when a request fails, marked so it never becomes context. */
export function errorTurn(message: string): Turn {
  return {
    role: "assistant",
    content: `**Error.** ${message}\n\n${ERROR_HINT}`,
    failed: true,
  };
}

/**
 * The turns worth replaying to the model as context.
 *
 * Failed turns are dropped. They are written by this client, not the model, so
 * sending them back teaches it that "**Error.** 500 ... Is Ollama running?" is
 * the sort of thing it says. It then has an error message in its own voice in
 * context, which is both wasted tokens and an invitation to imitate.
 *
 * Trace data is dropped too: the model produced it, and feeding it back lets a
 * tool summary be mistaken for an observation it made this turn.
 */
export function historyFor(turns: Turn[]): ChatMessage[] {
  return turns
    .filter((turn) => !turn.failed)
    .map(({ role, content }) => ({ role, content }));
}

/**
 * Whether a reply still belongs to the conversation on screen.
 *
 * "New chat" is reachable while a request is in flight, since the button
 * appears as soon as there is one turn. Without this check the answer to a
 * question the user has already cleared arrives in the empty conversation,
 * attached to nothing.
 */
export function isReplyCurrent(sentDuring: number, conversation: number): boolean {
  return sentDuring === conversation;
}
