/**
 * File management store with folder support.
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
	path: string;
}

export interface Folder {
	name: string;
	path: string;
	fileCount: number;
}

export const files = writable<GcodeFile[]>([]);
export const folders = writable<Folder[]>([]);
export const currentPath = writable<string>('');
export const parentPath = writable<string | null>(null);
export const filesLoading = writable<boolean>(false);

export async function refreshFiles(path = ''): Promise<void> {
	filesLoading.set(true);
	try {
		const data = await api.listFiles(path);
		files.set(data.files || []);
		folders.set(data.folders || []);
		currentPath.set(data.currentPath || '');
		parentPath.set(data.parentPath ?? null);
	} catch (e) {
		console.error('Failed to load files:', e);
	} finally {
		filesLoading.set(false);
	}
}
