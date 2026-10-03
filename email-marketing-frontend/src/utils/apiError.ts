export function getApiErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
    const err = error as { response?: { data?: Record<string, unknown> } };
    const data = err.response?.data;
    if (!data) {
        return fallback;
    }
    if (typeof data.detail === 'string') {
        return data.detail;
    }
    if (typeof data.error === 'string') {
        return data.error;
    }
    if (typeof data.message === 'string') {
        return data.message;
    }
    if (Array.isArray(data.non_field_errors) && data.non_field_errors.length) {
        return String(data.non_field_errors[0]);
    }
    const firstFieldError = Object.values(data).find(
        (value) => Array.isArray(value) && value.length,
    ) as string[] | undefined;
    if (firstFieldError?.length) {
        return String(firstFieldError[0]);
    }
    return fallback;
}
