import { useSyncExternalStore } from "react";
import type { ExtractResult } from "./types";

/**
 * Flow state between screens. The extract result is kept in sessionStorage so a refresh on the
 * check screen doesn't lose it; the File itself only lives in memory.
 */
interface FlowState {
  extract: ExtractResult | null;
  /** Full consumer number from this session's bill. Stored plans only keep it masked. */
  consumerNumber: string | null;
  /** Set when the user picks a language, so we stop suggesting one. */
  langChosen: boolean;
  /** Plan made in this session, so its page can show the full consumer number. */
  planId: string | null;
}

const KEY = "sbc.flow.v1";
const EMPTY: FlowState = { extract: null, consumerNumber: null, langChosen: false, planId: null };
let file: File | null = null;
let state: FlowState = load();
const listeners = new Set<() => void>();

function load(): FlowState {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw) return { ...EMPTY, ...JSON.parse(raw) };
  } catch {
    // storage blocked: start empty
  }
  return EMPTY;
}

function save() {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // ignore
  }
}

export function setFlow(patch: Partial<FlowState>) {
  state = { ...state, ...patch };
  save();
  listeners.forEach((l) => l());
}

export const getFlow = () => state;

export function useFlow() {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
  );
}

export function setPendingFile(f: File | null) {
  file = f;
}
export const getPendingFile = () => file;
