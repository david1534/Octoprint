import { writable } from 'svelte/store';

interface Toast {
	id: number;
	message: string;
	type: 'success' | 'error' | 'warning' | 'info';
	duration: number;
}

export const toasts = writable<Toast[]>([]);

let nextId = 0;

export function addToast(message: string, type: Toast['type'] = 'info', duration = 4000): void {
	const id = nextId++;
	toasts.update((t) => {
		const updated = [...t, { id, message, type, duration }];
		return updated.length > 5 ? updated.slice(-5) : updated;
	});
	if (duration > 0) {
		setTimeout(() => dismissToast(id), duration);
	}
}

export function dismissToast(id: number): void {
	toasts.update((t) => t.filter((toast) => toast.id !== id));
}

export const toast = {
	success: (msg: string) => addToast(msg, 'success'),
	error: (msg: string) => addToast(msg, 'error', 6000),
	warning: (msg: string) => addToast(msg, 'warning', 5000),
	info: (msg: string) => addToast(msg, 'info')
};
