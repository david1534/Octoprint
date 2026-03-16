/**
 * REST API client for the PrintForge backend.
 */

const BASE = '/api';
const DEFAULT_TIMEOUT = 15_000; // 15 seconds

async function request<T>(path: string, options?: RequestInit & { timeout?: number }): Promise<T> {
	const { timeout = DEFAULT_TIMEOUT, ...fetchOptions } = options || {};
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), timeout);

	try {
		const res = await fetch(`${BASE}${path}`, {
			headers: { 'Content-Type': 'application/json' },
			signal: controller.signal,
			...fetchOptions
		});
		if (!res.ok) {
			const error = await res.json().catch(() => ({ detail: res.statusText }));
			throw new Error(error.detail || `API error: ${res.status}`);
		}
		return res.json();
	} catch (e: any) {
		if (e.name === 'AbortError') {
			throw new Error('Request timed out. Check your connection and try again.');
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
	startPrint: (filename: string) =>
		post<any>('/printer/print', { filename }),
	pausePrint: () => post<any>('/printer/pause'),
	resumePrint: () => post<any>('/printer/resume'),
	cancelPrint: () => post<any>('/printer/cancel'),
	emergencyStop: () => post<any>('/printer/emergency-stop'),
	motorsOff: () => post<any>('/printer/motors-off'),
	getTemperatureHistory: () => request<any>('/printer/temperature/history'),

	// Files
	listFiles: () => request<any>('/files/'),
	uploadFile: async (file: File) => {
		const formData = new FormData();
		formData.append('file', file);
		const res = await fetch(`${BASE}/files/upload`, {
			method: 'POST',
			body: formData
		});
		if (!res.ok) {
			const error = await res.json().catch(() => ({ detail: res.statusText }));
			throw new Error(error.detail || 'Upload failed');
		}
		return res.json();
	},
	deleteFile: (filename: string) =>
		request<any>(`/files/${encodeURIComponent(filename)}`, { method: 'DELETE' }),
	getFileMetadata: (filename: string) =>
		request<any>(`/files/${encodeURIComponent(filename)}/metadata`),

	// System
	getHealth: () => request<any>('/system/health'),
	getSerialPorts: () => request<any>('/system/serial-ports'),
	getDiskUsage: () => request<any>('/system/disk-usage'),

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
		request<any>(`/history/${id}`, { method: 'DELETE' })
};
