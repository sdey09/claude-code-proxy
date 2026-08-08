import { create } from "zustand";

interface FiltersState {
  page: number;
  model: string;
  status: string;
  setFilters: (next: { model: string; status: string }) => void;
  setPage: (page: number) => void;
}

export const useFiltersStore = create<FiltersState>((set) => ({
  page: 1,
  model: "",
  status: "",
  setFilters: ({ model, status }) => set({ model, status, page: 1 }),
  setPage: (page) => set({ page }),
}));
