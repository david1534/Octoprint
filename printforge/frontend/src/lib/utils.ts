/**
 * Shared formatting and utility helpers.
 */

/** Format a byte count as a human-readable size string. */
export function formatFileSize(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

/** Format seconds into a concise duration string (e.g. "2h 15m" or "45m 30s"). */
export function formatDuration(seconds: number | null | undefined): string {
	if (!seconds || seconds <= 0) return '--';
	const h = Math.floor(seconds / 3600);
	const m = Math.floor((seconds % 3600) / 60);
	const s = Math.floor(seconds % 60);
	if (h > 0) return `${h}h ${m}m`;
	if (m > 0) return `${m}m ${s}s`;
	return `${s}s`;
}

/** Format a temperature reading with its target, e.g. "205/210°C". */
export function formatTemp(actual: number, target: number): string {
	return `${Math.round(actual)}/${Math.round(target)}°C`;
}

/** Format a date string or timestamp as a relative time ago string. */
export function formatTimeAgo(date: string | number | Date): string {
	const now = Date.now();
	const then = typeof date === 'string' ? new Date(date).getTime()
		: typeof date === 'number' ? date
		: date.getTime();
	const diff = Math.floor((now - then) / 1000);

	if (diff < 60) return 'just now';
	if (diff < 3600) {
		const m = Math.floor(diff / 60);
		return `${m}m ago`;
	}
	if (diff < 86400) {
		const h = Math.floor(diff / 3600);
		return `${h}h ago`;
	}
	if (diff < 172800) return 'yesterday';
	if (diff < 604800) {
		const d = Math.floor(diff / 86400);
		return `${d}d ago`;
	}
	const d = new Date(then);
	return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Clamp a number between min and max. */
export function clamp(value: number, min: number, max: number): number {
	return Math.min(Math.max(value, min), max);
}

/** Format seconds as a clock-style string (e.g. "1:23:45"). */
export function formatClock(seconds: number): string {
	const h = Math.floor(seconds / 3600);
	const m = Math.floor((seconds % 3600) / 60);
	const s = Math.floor(seconds % 60);
	if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
	return `${m}:${String(s).padStart(2, '0')}`;
}
