/**
 * File management store.
 */

import { writable } from 'svelte/store';
import { api } from '../api';

// Re-export shared utils for backward compatibility
export { formatFileSize, formatDuration } from '../utils';

export interface GcodeFile {
	filename: string;
	fileSize: number;
	totalLines: number;
	printableLines: number;
	estimatedTime: number | null;
	filamentUsedMm: number | null;
	filamentUsedGrams: number | null;
	layerCount: number;
	slicer: string | null;
	nozzleTemp: number | null;
	bedTemp: number | null;
}

export const files = writable<GcodeFile[]>([]);
export const filesLoading = writable<boolean>(false);

export async function refreshFiles(): Promise<void> {
	filesLoading.set(true);
	try {
		const data = await api.listFiles();
		files.set(data.files || []);
	} catch (e) {
		console.error('Failed to load files:', e);
	} finally {
		filesLoading.set(false);
	}
}
