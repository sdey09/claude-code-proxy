import { create } from "zustand";

interface UiState {
  showRawByKey: Record<string, boolean>;
  toggleShowRaw: (key: string) => void;
}

export const useUiStore = create<UiState>((set) => ({
  showRawByKey: {},
  toggleShowRaw: (key) =>
    set((state) => ({ showRawByKey: { ...state.showRawByKey, [key]: !state.showRawByKey[key] } })),
}));
