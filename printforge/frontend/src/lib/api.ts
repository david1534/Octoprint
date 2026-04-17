/**
 * REST API client for the PrintForge backend.
 */

const BASE = '/api';
const DEFAULT_TIMEOUT = 15_000; // 15 seconds

/** Get stored API key for authenticated requests. */
function getApiKey(): string | null {
	if (typeof localStorage === 'undefined') return null;
	return localStorage.getItem('printforge:apiKey');
}

/** Store API key in localStorage. */
export function setApiKey(key: string | null) {
	if (typeof localStorage === 'undefined') return;
	if (key) {
		localStorage.setItem('printforge:apiKey', key);
	} else {
		localStorage.removeItem('printforge:apiKey');
	}
}

async function request<T>(path: string, options?: RequestInit & { timeout?: number }): Promise<T> {
	const { timeout = DEFAULT_TIMEOUT, ...fetchOptions } = options || {};
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), timeout);

	// Build headers with optional API key
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	const apiKey = getApiKey();
	if (apiKey) {
		headers['Authorization'] = `Bearer ${apiKey}`;
	}

	try {
		const res = await fetch(`${BASE}${path}`, {
			headers,
			signal: controller.signal,
			...fetchOptions
		});
		if (!res.ok) {
			const error = await res.json().catch(() => ({ detail: res.statusText }));
			const detail = error.detail || `API error: ${res.status}`;
			// Provide user-friendly messages for common HTTP errors
			if (res.status === 404) throw new Error('Resource not found');
			if (res.status === 503) throw new Error('Service unavailable. The server may be restarting.');
			if (res.status === 500) throw new Error(`Internal Server Error: ${detail}`);
			throw new Error(detail);
		}
		return res.json();
	} catch (e: any) {
		if (e.name === 'AbortError') {
			throw new Error('Request timed out. Check your connection and try again.');
		}
		if (e.name === 'TypeError' && e.message?.includes('fetch')) {
			throw new Error('Connection failed. Check your network and try again.');
		}
		throw e;
	} finally {
		clearTimeout(timer);
	}
}

function post<T>(path: string, body?: object): Promise<T> {
	return request<T>(path, {
		method: 'POST',
		body: body ? JSON.stringify(body) : undefined
	});
}

export const api = {
	// Printer
	getState: () => request<any>('/printer/state'),
	connect: (port: string, baudrate: number) =>
		post<any>('/printer/connect', { port, baudrate }),
	disconnect: () => post<any>('/printer/disconnect'),
	home: (axes = 'XYZ') => post<any>(`/printer/home?axes=${axes}`),
	setTemperature: (hotend?: number, bed?: number, wait = false) =>
		post<any>('/printer/temperature', { hotend, bed, wait }),
	jog: (x = 0, y = 0, z = 0, feedrate = 3000) =>
		post<any>('/printer/jog', { x, y, z, feedrate }),
	extrude: (length: number, feedrate = 300) =>
		post<any>('/printer/extrude', { length, feedrate }),
	setFan: (speed: number) => post<any>('/printer/fan', { speed }),
	sendCommand: (command: string) =>
		post<any>('/printer/command', { command }),
	startPrint: (filename: string, spool_id?: number) =>
		post<any>('/printer/print', { filename, ...(spool_id != null ? { spool_id } : {}) }),
	pausePrint: () => post<any>('/printer/pause'),
	resumePrint: () => post<any>('/printer/resume'),
	cancelPrint: () => post<any>('/printer/cancel'),
	emergencyStop: () => post<any>('/printer/emergency-stop'),
	motorsOff: () => post<any>('/printer/motors-off'),
	getTemperatureHistory: () => request<any>('/printer/temperature/history'),

	// Files (with folder support)
	listFiles: (path = '') => request<any>(`/files/?path=${encodeURIComponent(path)}`),
	createFolder: (path: string) =>
		request<any>(`/files/folder?path=${encodeURIComponent(path)}`, { method: 'POST' }),
	deleteFolder: (path: string, force = false) =>
		request<any>(`/files/folder?path=${encodeURIComponent(path)}&force=${force}`, { method: 'DELETE' }),
	moveFile: (src: string, dest: string) =>
		request<any>(`/files/move?src=${encodeURIComponent(src)}&dest=${encodeURIComponent(dest)}`, { method: 'POST' }),
	moveFolder: (src: string, dest: string) =>
		request<any>(`/files/move-folder?src=${encodeURIComponent(src)}&dest=${encodeURIComponent(dest)}`, { method: 'POST' }),
	listAllFolders: () => request<any>('/files/all-folders'),
	renameFile: (src: string, name: string) =>
		request<any>(`/files/rename?src=${encodeURIComponent(src)}&name=${encodeURIComponent(name)}`, { method: 'POST' }),
	renameFolder: (src: string, name: string) =>
		request<any>(`/files/rename-folder?src=${encodeURIComponent(src)}&name=${encodeURIComponent(name)}`, { method: 'POST' }),
	uploadFile: async (file: File, path = '') => {
		const formData = new FormData();
		formData.append('file', file);
		const uploadHeaders: Record<string, string> = {};
		const apiKey = getApiKey();
		if (apiKey) uploadHeaders['Authorization'] = `Bearer ${apiKey}`;
		const res = await fetch(`${BASE}/files/upload?path=${encodeURIComponent(path)}`, {
			method: 'POST',
			headers: uploadHeaders,
			body: formData
		});
		if (!res.ok) {
			const error = await res.json().catch(() => ({ detail: res.statusText }));
			throw new Error(error.detail || 'Upload failed');
		}
		return res.json();
	},
	deleteFile: (filePath: string) =>
		request<any>(`/files/${encodeURIComponent(filePath)}`, { method: 'DELETE' }),
	getFileMetadata: (filePath: string) =>
		request<any>(`/files/${encodeURIComponent(filePath)}/metadata`),

	// System
	getHealth: () => request<any>('/system/health'),
	getSerialPorts: () => request<any>('/system/serial-ports'),
	getDiskUsage: () => request<any>('/system/disk-usage'),

	// Timelapse
	listTimelapses: () => request<any>('/timelapse/'),
	deleteTimelapse: (filename: string) =>
		request<any>(`/timelapse/${encodeURIComponent(filename)}`, { method: 'DELETE' }),
	getTimelapseVideoUrl: (filename: string) =>
		`${BASE}/timelapse/video/${encodeURIComponent(filename)}`,
	getTimelapseThumbnailUrl: (filename: string) =>
		`${BASE}/timelapse/thumbnail/${encodeURIComponent(filename)}`,
	getTimelapseRecordingStatus: () => request<any>('/timelapse/recording/status'),
	updateTimelapseSettings: (settings: {
		enabled?: boolean;
		captureMode?: string;
		captureInterval?: number;
		renderFps?: number;
	}) => request<any>('/timelapse/recording/settings', {
		method: 'PUT',
		body: JSON.stringify(settings),
	}),
	testTimelapseCapture: () => post<any>('/timelapse/recording/test-capture'),

	// Settings
	getSettings: () => request<any>('/settings/'),
	updateSettings: (settings: Record<string, string>) =>
		request<any>('/settings/', { method: 'PUT', body: JSON.stringify(settings) }),

	// API key management
	getApiKeyStatus: () => request<any>('/settings/api-key/status'),
	generateApiKey: () => post<any>('/settings/api-key/generate'),
	revokeApiKey: () => request<any>('/settings/api-key', { method: 'DELETE' }),

	// Push notifications (ntfy)
	testNotification: () => post<any>('/notifications/test'),

	// System power controls
	restartService: () => post<any>('/system/restart-service'),
	restartOS: () => post<any>('/system/restart-os'),
	shutdownOS: () => post<any>('/system/shutdown-os'),

	// Staging → production promote (only works on staging instance)
	promoteStagingToProduction: (force = false) =>
		post<any>(`/system/promote${force ? '?force=true' : ''}`),

	// Filament spools
	getSpools: () => request<any>('/filament/'),
	createSpool: (data: { name: string; material: string; color: string; total_weight_g: number; cost_per_kg: number; notes?: string }) =>
		post<any>('/filament/', data),
	getActiveSpool: () => request<any>('/filament/active'),
	activateSpool: (id: number) => post<any>(`/filament/${id}/activate`),
	updateSpool: (id: number, data: Record<string, any>) =>
		request<any>(`/filament/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
	deductFilament: (id: number, grams: number) =>
		post<any>(`/filament/${id}/deduct`, { grams }),
	deleteSpool: (id: number) =>
		request<any>(`/filament/${id}`, { method: 'DELETE' }),
	getLowFilamentWarnings: () => request<any>('/filament/warnings'),

	// Bed mesh
	getBedMesh: () => request<any>('/printer/bed-mesh'),
	probeBedMesh: () => post<any>('/printer/bed-mesh/probe'),

	// Camera
	getCameraUrls: () => request<any>('/camera/stream'),

	// History
	getHistory: (limit = 20, offset = 0, status?: string) => {
		let url = `/history/?limit=${limit}&offset=${offset}`;
		if (status) url += `&status=${status}`;
		return request<any>(url);
	},
	getHistoryStats: () => request<any>('/history/stats'),
	deleteHistoryEntry: (id: number) =>
		request<any>(`/history/${id}`, { method: 'DELETE' }),

	// Errors
	getErrors: (activeOnly = false) =>
		request<any>(`/errors/${activeOnly ? '?active_only=true' : ''}`),
	dismissError: (id: number) => post<any>(`/errors/${id}/dismiss`),
	dismissAllErrors: () => post<any>('/errors/dismiss-all'),
	clearErrors: () => post<any>('/errors/clear')
};
