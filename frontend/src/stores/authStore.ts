import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../services/api';

interface User {
  id: number;
  username: string;
  email: string;
  real_name: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  avatar_url?: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string, location?: { latitude: number; longitude: number }) => Promise<void>;
  logout: () => void;
  updateUser: (user: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      login: async (username, password, location) => {
        const response = await api.post('/auth/login', {
          username,
          password,
          location,
        });
        
        const { access_token, refresh_token, user } = response.data;
        
        set({
          user,
          accessToken: access_token,
          refreshToken: refresh_token,
          isAuthenticated: true,
        });
        
        // 设置 axios 默认 header
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      },

      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
        delete api.defaults.headers.common['Authorization'];
      },

      updateUser: (userData) => {
        const currentUser = get().user;
        if (currentUser) {
          set({ user: { ...currentUser, ...userData } });
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// 初始化时恢复 token
const { accessToken } = useAuthStore.getState();
if (accessToken) {
  api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;
}
