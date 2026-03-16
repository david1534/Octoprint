import { writable } from 'svelte/store';

interface ConfirmState {
	open: boolean;
	title: string;
	message: string;
	confirmLabel: string;
	variant: 'danger' | 'primary';
	resolve: ((value: boolean) => void) | null;
}

export const confirmState = writable<ConfirmState>({
	open: false,
	title: '',
	message: '',
	confirmLabel: 'Confirm',
	variant: 'primary',
	resolve: null
});

export function confirmAction(opts: {
	title: string;
	message: string;
	confirmLabel?: string;
	variant?: 'danger' | 'primary';
}): Promise<boolean> {
	return new Promise((resolve) => {
		confirmState.set({
			open: true,
			title: opts.title,
			message: opts.message,
			confirmLabel: opts.confirmLabel || 'Confirm',
			variant: opts.variant || 'primary',
			resolve
		});
	});
}

export function resolveConfirm(value: boolean): void {
	confirmState.update((s) => {
		s.resolve?.(value);
		return { ...s, open: false, resolve: null };
	});
}
