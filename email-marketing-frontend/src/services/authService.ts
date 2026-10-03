import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

const setTokens = (access: string, refresh: string) => {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
};

export const authService = {
    async register(email: string, password: string, firstName: string, lastName: string) {
        const response = await axios.post(`${API_BASE_URL}/auth/register/`, {
            email,
            password,
            password2: password,
            first_name: firstName,
            last_name: lastName,
            username: email,
        });
        if (response.data?.tokens?.access && response.data?.tokens?.refresh) {
            setTokens(response.data.tokens.access, response.data.tokens.refresh);
        }
        return response.data;
    },

    async login(email: string, password: string) {
        const response = await axios.post(`${API_BASE_URL}/token/`, {
            username: email,
            password,
        });
        setTokens(response.data.access, response.data.refresh);
        return response.data;
    },

    async logout() {
        try {
            const token = localStorage.getItem('access_token');
            const refreshToken = localStorage.getItem('refresh_token');
            if (token) {
                await axios.post(
                    `${API_BASE_URL}/auth/logout/`,
                    { refresh_token: refreshToken },
                    {
                        headers: {
                            Authorization: `Bearer ${token}`,
                        },
                    }
                );
            }
        } finally {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
        }
    },

    async getProfile() {
        const token = localStorage.getItem('access_token');
        const response = await axios.get(`${API_BASE_URL}/auth/profile/`, {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });
        return response.data;
    },

    isAuthenticated() {
        return !!localStorage.getItem('access_token');
    },
};
