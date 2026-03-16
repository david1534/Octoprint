<script lang="ts">
	import { fade, fly } from 'svelte/transition';

	type NotificationType = 'info' | 'success' | 'warning' | 'error';

	interface Notification {
		id: string;
		type: NotificationType;
		title: string;
		message: string;
		timestamp: Date;
		read: boolean;
	}

	let open = $state(false);

	let notifications = $state<Notification[]>([
		{
			id: '1',
			type: 'success',
			title: 'Print Complete',
			message: 'benchy_v2.gcode finished successfully.',
			timestamp: new Date(Date.now() - 1000 * 60 * 4),
			read: false
		},
		{
			id: '2',
			type: 'warning',
			title: 'Thermal Runaway Warning',
			message: 'Hotend temperature exceeded target by 8\u00b0C.',
			timestamp: new Date(Date.now() - 1000 * 60 * 23),
			read: false
		},
		{
			id: '3',
			type: 'error',
			title: 'Print Failed',
			message: 'cable_clip.gcode stopped due to communication error.',
			timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2),
			read: false
		},
		{
			id: '4',
			type: 'info',
			title: 'Firmware Update Available',
			message: 'Marlin 2.1.3 is available for your printer.',
			timestamp: new Date(Date.now() - 1000 * 60 * 60 * 5),
			read: true
		},
		{
			id: '5',
			type: 'success',
			title: 'Bed Leveling Complete',
			message: 'Auto bed leveling mesh calibrated successfully.',
			timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24),
			read: true
		}
	]);

	let unreadCount = $derived(notifications.filter((n) => !n.read).length);

	const typeStyles: Record<NotificationType, { bg: string; text: string; icon: string }> = {
		success: {
			bg: 'bg-emerald-500/15',
			text: 'text-emerald-400',
			icon: 'M5 13l4 4L19 7'
		},
		warning: {
			bg: 'bg-amber-500/15',
			text: 'text-amber-400',
			icon: 'M12 9v2m0 4h.01M12 3l9.5 16.5H2.5L12 3z'
		},
		error: {
			bg: 'bg-red-500/15',
			text: 'text-red-400',
			icon: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
		},
		info: {
			bg: 'bg-accent/15',
			text: 'text-accent',
			icon: 'M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z'
		}
	};

	function toggle() {
		open = !open;
	}

	function close() {
		open = false;
	}

	function markAllRead() {
		notifications = notifications.map((n) => ({ ...n, read: true }));
	}

	function markRead(id: string) {
		notifications = notifications.map((n) => (n.id === id ? { ...n, read: true } : n));
	}

	function dismiss(id: string) {
		notifications = notifications.filter((n) => n.id !== id);
	}

	function formatTimestamp(date: Date): string {
		const now = Date.now();
		const diff = now - date.getTime();
		const seconds = Math.floor(diff / 1000);
		const minutes = Math.floor(seconds / 60);
		const hours = Math.floor(minutes / 60);
		const days = Math.floor(hours / 24);

		if (minutes < 1) return 'just now';
		if (minutes < 60) return `${minutes}m ago`;
		if (hours < 24) return `${hours}h ago`;
		if (days === 1) return 'yesterday';
		return `${days}d ago`;
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) {
			close();
		}
	}
</script>

<svelte:window onkeydown={onKeydown} />

<div class="relative">
	<!-- Bell trigger button -->
	<button
		class="relative p-2 rounded-lg transition-colors duration-150
			   hover:bg-surface-700 text-surface-400 hover:text-surface-100
			   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
		onclick={toggle}
		aria-label="Notifications"
		aria-expanded={open}
		aria-haspopup="true"
	>
		<!-- Bell icon -->
		<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="1.5"
				d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
			/>
		</svg>

		<!-- Unread count badge -->
		{#if unreadCount > 0}
			<span
				class="absolute -top-0.5 -right-0.5 flex items-center justify-center
					   min-w-[18px] h-[18px] px-1 rounded-full
					   bg-red-500 text-white text-[10px] font-bold
					   ring-2 ring-surface-900"
			>
				{unreadCount > 9 ? '9+' : unreadCount}
			</span>
		{/if}
	</button>

	<!-- Dropdown panel -->
	{#if open}
		<!-- Backdrop (click outside to close) -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="fixed inset-0 z-40" onclick={close} onkeydown={() => {}}></div>

		<div
			class="absolute right-0 top-full mt-2 z-50
				   w-[360px] sm:w-[400px] max-h-[480px]
				   bg-surface-900 border border-surface-700 rounded-xl shadow-2xl shadow-black/40
				   flex flex-col overflow-hidden"
			transition:fly={{ y: -8, duration: 200 }}
			role="menu"
			aria-label="Notifications"
		>
			<!-- Header -->
			<div class="flex items-center justify-between px-4 py-3 border-b border-surface-700">
				<div class="flex items-center gap-2">
					<h3 class="text-sm font-semibold text-surface-100">Notifications</h3>
					{#if unreadCount > 0}
						<span class="badge bg-accent/15 text-accent">
							{unreadCount} new
						</span>
					{/if}
				</div>
				{#if unreadCount > 0}
					<button
						class="text-xs font-medium text-accent hover:text-accent-hover transition-colors duration-150
							   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
						onclick={markAllRead}
					>
						Mark all as read
					</button>
				{/if}
			</div>

			<!-- Notification list -->
			<div class="flex-1 overflow-y-auto overscroll-contain divide-y divide-surface-800">
				{#if notifications.length === 0}
					<!-- Empty state -->
					<div class="flex flex-col items-center justify-center py-12 text-center px-4">
						<svg class="w-10 h-10 text-surface-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="1.5"
								d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
							/>
						</svg>
						<p class="text-sm font-medium text-surface-400">No notifications</p>
						<p class="text-xs text-surface-500 mt-1">You're all caught up.</p>
					</div>
				{:else}
					{#each notifications as notification (notification.id)}
						<div
							class="group relative flex gap-3 px-4 py-3 transition-colors duration-150
								   hover:bg-surface-800/60
								   {notification.read ? 'opacity-60' : ''}"
							role="menuitem"
						>
							<!-- Unread indicator -->
							{#if !notification.read}
								<div class="absolute left-1.5 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-accent"></div>
							{/if}

							<!-- Type icon -->
							<div
								class="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center mt-0.5
									   {typeStyles[notification.type].bg}"
							>
								<svg
									class="w-4 h-4 {typeStyles[notification.type].text}"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d={typeStyles[notification.type].icon}
									/>
								</svg>
							</div>

							<!-- Content -->
							<button
								class="flex-1 min-w-0 text-left"
								onclick={() => markRead(notification.id)}
							>
								<div class="flex items-baseline justify-between gap-2">
									<p class="text-sm font-medium text-surface-100 truncate">
										{notification.title}
									</p>
									<span class="shrink-0 text-[11px] tabular-nums text-surface-500">
										{formatTimestamp(notification.timestamp)}
									</span>
								</div>
								<p class="text-xs text-surface-400 mt-0.5 line-clamp-2">
									{notification.message}
								</p>
							</button>

							<!-- Dismiss button -->
							<button
								class="shrink-0 self-start mt-1 p-1 rounded-md
									   opacity-0 group-hover:opacity-100
									   text-surface-500 hover:text-surface-200 hover:bg-surface-700
									   transition-all duration-150
									   focus-visible:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
								onclick={() => dismiss(notification.id)}
								aria-label="Dismiss notification"
							>
								<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
								</svg>
							</button>
						</div>
					{/each}
				{/if}
			</div>

			<!-- Footer -->
			{#if notifications.length > 0}
				<div class="border-t border-surface-700 px-4 py-2.5">
					<button
						class="w-full text-xs font-medium text-surface-400 hover:text-surface-200 transition-colors duration-150 text-center py-1
							   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent rounded"
						onclick={close}
					>
						View all notifications
					</button>
				</div>
			{/if}
		</div>
	{/if}
</div>
