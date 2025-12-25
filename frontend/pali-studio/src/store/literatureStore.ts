/**
 * Literature state management with Zustand
 */
import { create } from 'zustand';
import type { Literature, Segment, PitakaStructure } from '@/types/literature';
import { getSegments, searchSegments } from '@/api/literature';

interface SearchMeta {
  returned_count: number;
  hit_segments_count: number;
  total_occurrences: number;
  unknown_page_occurrences: number;
  pages: Array<{ page_number: number; occurrences: number }>;
}

interface LiteratureState {
  // State
  literatures: Literature[];
  pitakaStructure: PitakaStructure | null;
  currentLiterature: Literature | null;
  segments: Segment[];
  currentSegment: Segment | null;
  isLoading: boolean;
  error: string | null;

  // Pagination
  totalSegments: number;
  currentOffset: number;
  currentLimit: number;

  // Location state (Vagga/Sutta filtering)
  currentVaggaId: number | null;
  currentSuttaId: number | null;

  // Multi-select mode
  isSelectMode: boolean;
  selectedSegmentIds: Set<number>;
  lastSelectedSegmentId: number | null;

  // Search
  isSearchMode: boolean;
  searchQuery: string;
  searchPage: number | null;
  searchResults: Segment[];
  searchMeta: SearchMeta | null;

  // Translation progress tracking
  translatingSegmentIds: Set<number>;

  // Actions
  setLiteratures: (literatures: Literature[], structure: PitakaStructure) => void;
  selectLiterature: (literature: Literature | null) => void;
  setSegments: (segments: Segment[], total: number, offset: number) => void;
  appendSegments: (segments: Segment[]) => void;
  selectSegment: (segment: Segment | null) => void;
  updateSegmentTranslation: (segmentId: number, translation: Segment['translation']) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setCurrentLocation: (vaggaId: number | null, suttaId: number | null) => void;
  loadSegmentsForLocation: (literatureId: string, vaggaId: number | null, suttaId: number | null) => Promise<void>;
  // Multi-select actions
  toggleSelectMode: () => void;
  toggleSegmentSelection: (segmentId: number) => void;
  selectRange: (fromSegmentId: number, toSegmentId: number) => void;
  selectConsecutiveSegments: (segmentId: number, count?: number) => void;
  selectAllUntranslated: () => void;
  clearSelection: () => void;
  // Search actions
  performSearch: (literatureId: string, query: string, options?: { page?: number | null }) => Promise<void>;
  clearSearch: () => void;
  // Translation tracking actions
  startTranslating: (segmentId: number) => void;
  stopTranslating: (segmentId: number) => void;
  reset: () => void;
}

const initialState = {
  literatures: [],
  pitakaStructure: null,
  currentLiterature: null,
  segments: [],
  currentSegment: null,
  isLoading: false,
  error: null,
  totalSegments: 0,
  currentOffset: 0,
  currentLimit: 50,
  currentVaggaId: null as number | null,
  currentSuttaId: null as number | null,
  isSelectMode: false,
  selectedSegmentIds: new Set<number>(),
  lastSelectedSegmentId: null as number | null,
  isSearchMode: false,
  searchQuery: '',
  searchPage: null as number | null,
  searchResults: [] as Segment[],
  searchMeta: null as SearchMeta | null,
  translatingSegmentIds: new Set<number>(),
};

export const useLiteratureStore = create<LiteratureState>((set) => ({
  ...initialState,

  setLiteratures: (literatures, structure) =>
    set({ literatures, pitakaStructure: structure }),

  selectLiterature: (literature) =>
    set({
      currentLiterature: literature,
      segments: [],
      currentSegment: null,
      currentOffset: 0,
      totalSegments: 0,
      currentVaggaId: null,
      currentSuttaId: null,
      isSelectMode: false,
      selectedSegmentIds: new Set<number>(),
      lastSelectedSegmentId: null,
      isSearchMode: false,
      searchQuery: '',
      searchPage: null,
      searchResults: [],
      searchMeta: null,
    }),

  setSegments: (segments, total, offset) =>
    set({
      segments,
      totalSegments: total,
      currentOffset: offset,
    }),

  appendSegments: (newSegments) =>
    set((state) => ({
      segments: [...state.segments, ...newSegments],
      currentOffset: state.currentOffset + newSegments.length,
    })),

  selectSegment: (segment) =>
    set({
      currentSegment: segment,
      lastSelectedSegmentId: segment ? segment.id : null,
    }),

  updateSegmentTranslation: (segmentId, translation) =>
    set((state) => ({
      segments: state.segments.map((seg) =>
        seg.id === segmentId
          ? { ...seg, translation, is_translated: true }
          : seg
      ),
      currentSegment:
        state.currentSegment?.id === segmentId
          ? { ...state.currentSegment, translation, is_translated: true }
          : state.currentSegment,
    })),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),

  setCurrentLocation: (vaggaId, suttaId) =>
    set({
      currentVaggaId: vaggaId,
      currentSuttaId: suttaId,
    }),

  loadSegmentsForLocation: async (literatureId, vaggaId, suttaId) => {
    set({ isLoading: true, error: null });
    try {
      const data = await getSegments(literatureId, {
        offset: 0,
        limit: 50,
        vagga_id: vaggaId ?? undefined,
        sutta_id: suttaId ?? undefined,
      });
      set({
        segments: data.segments,
        totalSegments: data.pagination.total,
        currentOffset: 0,
        currentVaggaId: vaggaId,
        currentSuttaId: suttaId,
        isLoading: false,
      });
    } catch (err) {
      set({ error: (err as Error).message, isLoading: false });
    }
  },

  // Multi-select actions
  toggleSelectMode: () =>
    set((state) => ({
      isSelectMode: !state.isSelectMode,
      selectedSegmentIds: state.isSelectMode ? new Set<number>() : state.selectedSegmentIds,
      lastSelectedSegmentId: state.isSelectMode ? null : state.lastSelectedSegmentId,
    })),

  toggleSegmentSelection: (segmentId) =>
    set((state) => {
      const newSelected = new Set(state.selectedSegmentIds);
      if (newSelected.has(segmentId)) {
        newSelected.delete(segmentId);
        return { selectedSegmentIds: newSelected, lastSelectedSegmentId: segmentId };
      } else {
        // Limit to max 20 selections for batch translation
        if (newSelected.size >= 20) {
          return state; // Don't add more if already at limit
        }
        newSelected.add(segmentId);
      }
      return { selectedSegmentIds: newSelected, lastSelectedSegmentId: segmentId };
    }),

  selectRange: (fromSegmentId, toSegmentId) =>
    set((state) => {
      // Find indices of the two segments
      const fromIndex = state.segments.findIndex((s) => s.id === fromSegmentId);
      const toIndex = state.segments.findIndex((s) => s.id === toSegmentId);

      if (fromIndex === -1 || toIndex === -1) return state;

      // Determine range direction
      const startIndex = Math.min(fromIndex, toIndex);
      const endIndex = Math.max(fromIndex, toIndex);

      // Select all untranslated segments in range (up to 20)
      const newSelected = new Set(state.selectedSegmentIds);
      for (let i = startIndex; i <= endIndex && newSelected.size < 20; i++) {
        const segment = state.segments[i];
        if (!segment.is_translated) {
          newSelected.add(segment.id);
        }
      }

      return {
        isSelectMode: true,
        selectedSegmentIds: newSelected,
        lastSelectedSegmentId: toSegmentId,
      };
    }),

  selectConsecutiveSegments: (segmentId, count = 5) =>
    set((state) => {
      // Find the index of the clicked segment
      const startIndex = state.segments.findIndex((s) => s.id === segmentId);
      if (startIndex === -1) return state;

      // Select up to 'count' consecutive untranslated segments starting from clicked one
      const newSelected = new Set<number>();
      let selectedCount = 0;

      for (let i = startIndex; i < state.segments.length && selectedCount < count; i++) {
        const segment = state.segments[i];
        if (!segment.is_translated) {
          newSelected.add(segment.id);
          selectedCount++;
        }
      }

      return {
        isSelectMode: true,
        selectedSegmentIds: newSelected,
      };
    }),

  selectAllUntranslated: () =>
    set((state) => ({
      selectedSegmentIds: new Set(
        state.segments.filter((s) => !s.is_translated).map((s) => s.id)
      ),
    })),

  clearSelection: () => set({ selectedSegmentIds: new Set<number>(), lastSelectedSegmentId: null }),

  // Search actions
  performSearch: async (literatureId, query, options = {}) => {
    const trimmed = query.trim();
    const page = options.page ?? null;

    if (!trimmed) {
      set({ isSearchMode: false, searchQuery: '', searchPage: null, searchResults: [], searchMeta: null });
      return;
    }

    set({ isLoading: true, error: null, searchQuery: trimmed, searchPage: page });
    try {
      const data = await searchSegments(literatureId, trimmed, { page: page ?? undefined });
      set({
        isSearchMode: true,
        searchResults: data.results,
        searchMeta: {
          returned_count: data.returned_count,
          hit_segments_count: data.hit_segments_count,
          total_occurrences: data.total_occurrences,
          unknown_page_occurrences: data.unknown_page_occurrences,
          pages: data.pages,
        },
        searchPage: data.page_filter,
        isLoading: false,
      });
    } catch (err) {
      set({ error: (err as Error).message, isLoading: false });
    }
  },

  clearSearch: () =>
    set({
      isSearchMode: false,
      searchQuery: '',
      searchPage: null,
      searchResults: [],
      searchMeta: null,
    }),

  // Translation tracking actions
  startTranslating: (segmentId) =>
    set((state) => {
      const newSet = new Set(state.translatingSegmentIds);
      newSet.add(segmentId);
      return { translatingSegmentIds: newSet };
    }),

  stopTranslating: (segmentId) =>
    set((state) => {
      const newSet = new Set(state.translatingSegmentIds);
      newSet.delete(segmentId);
      return { translatingSegmentIds: newSet };
    }),

  reset: () => set(initialState),
}));
