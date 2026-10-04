import { create } from 'zustand';

interface UiState {
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  closeSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  /** Drawer del Sidebar en móvil (`<sm`), que sí es un overlay y queda por debajo del
   *  `z-50` del banner de instalación. Vive aparte de `isSidebarOpen` porque en `≥sm` ese
   *  estado está forzado en `true` (el sidebar colapsable no es un overlay): usarlo como
   *  señal apagaría el banner para siempre en desktop. Lo publica el `matchMedia` que ya
   *  vive en el layout del dashboard. */
  isMobileDrawerOpen: boolean;
  setMobileDrawerOpen: (open: boolean) => void;
  /** Diálogos abiertos a la vez (Fase 33 F6, QA-034): el banner de instalación comparte
   *  `z-50` con sus overlays y, al ir después en el DOM, tapaba el botón "Guardar" del
   *  modal en móvil. */
  openDialogs: number;
  openDialog: () => void;
  closeDialog: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  isSidebarOpen: true,
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  closeSidebar: () => set({ isSidebarOpen: false }),
  setSidebarOpen: (open) => set({ isSidebarOpen: open }),
  isMobileDrawerOpen: false,
  setMobileDrawerOpen: (open) => set({ isMobileDrawerOpen: open }),
  openDialogs: 0,
  openDialog: () => set((state) => ({ openDialogs: state.openDialogs + 1 })),
  closeDialog: () => set((state) => ({ openDialogs: state.openDialogs - 1 })),
}));
