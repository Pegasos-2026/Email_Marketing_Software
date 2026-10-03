import React, { createContext, useContext, useEffect, useState } from 'react';
import { authService } from '../services/authService';

interface AuthContextValue {
    user: any;
    loading: boolean;
    isAuthenticated: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, password: string, firstName: string, lastName: string) => Promise<void>;
    logout: () => Promise<void>;
    reloadProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<any>(null);
    const [isAuthenticated, setIsAuthenticated] = useState(authService.isAuthenticated());
    const [loading, setLoading] = useState(true);

    const reloadProfile = async () => {
        try {
            const profile = await authService.getProfile();
            setUser(profile);
        } catch (error) {
            setUser(null);
            setIsAuthenticated(false);
        }
    };

    useEffect(() => {
        const init = async () => {
            if (authService.isAuthenticated()) {
                await reloadProfile();
            }
            setLoading(false);
        };
        init();
    }, []);

    const login = async (email: string, password: string) => {
        await authService.login(email, password);
        setIsAuthenticated(true);
        await reloadProfile();
    };

    const register = async (email: string, password: string, firstName: string, lastName: string) => {
        await authService.register(email, password, firstName, lastName);
        setIsAuthenticated(true);
        await reloadProfile();
    };

    const logout = async () => {
        await authService.logout();
        setUser(null);
        setIsAuthenticated(false);
    };

    return (
        <AuthContext.Provider value={{ user, loading, isAuthenticated, login, register, logout, reloadProfile }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = (): AuthContextValue => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider');
    }
    return context;
};
