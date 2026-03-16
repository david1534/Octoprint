<script lang="ts">
	import { fade, slide } from 'svelte/transition';

	// Sidebar navigation sections
	const sections = [
		{ id: 'profile', label: 'Profile', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
		{ id: 'account', label: 'Account', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
		{ id: 'notifications', label: 'Notifications', icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' },
		{ id: 'appearance', label: 'Appearance', icon: 'M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01' }
	] as const;

	type SectionId = typeof sections[number]['id'];

	let activeSection = $state<SectionId>('profile');
	let mobileMenuOpen = $state(false);

	// Profile form state
	let profileName = $state('');
	let profileEmail = $state('');
	let profileBio = $state('');
	let avatarPreview = $state<string | null>(null);
	let avatarInput = $state<HTMLInputElement | null>(null);
	let saving = $state(false);

	// Account form state
	let currentPassword = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');

	// Notification settings state
	let emailNotifications = $state(true);
	let pushNotifications = $state(false);
	let printCompleteNotify = $state(true);
	let errorNotify = $state(true);
	let updateNotify = $state(false);

	// Appearance state
	let theme = $state<'dark' | 'light' | 'system'>('dark');
	let fontSize = $state<'small' | 'default' | 'large'>('default');

	function selectSection(id: SectionId) {
		activeSection = id;
		mobileMenuOpen = false;
	}

	function handleAvatarClick() {
		avatarInput?.click();
	}

	function handleAvatarChange(e: Event) {
		const target = e.target as HTMLInputElement;
		const file = target.files?.[0];
		if (!file) return;

		if (!file.type.startsWith('image/')) return;

		const reader = new FileReader();
		reader.onload = () => {
			avatarPreview = reader.result as string;
		};
		reader.readAsDataURL(file);
	}

	function removeAvatar() {
		avatarPreview = null;
		if (avatarInput) avatarInput.value = '';
	}

	async function saveProfile() {
		saving = true;
		// Simulate save
		await new Promise((r) => setTimeout(r, 800));
		saving = false;
	}
</script>

<svelte:head>
	<title>PrintForge - Settings</title>
</svelte:head>

<!-- Page header -->
<div class="mb-6">
	<h1 class="text-2xl font-bold">Settings</h1>
	<p class="mt-1 text-sm text-surface-400">Manage your profile, account, and preferences.</p>
</div>

<div class="flex flex-col lg:flex-row gap-6">
	<!-- Mobile section selector -->
	<div class="lg:hidden">
		<button
			class="w-full flex items-center justify-between card px-4 py-3"
			onclick={() => mobileMenuOpen = !mobileMenuOpen}
			aria-expanded={mobileMenuOpen}
			aria-controls="settings-nav-mobile"
		>
			<div class="flex items-center gap-3">
				<svg class="w-5 h-5 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={sections.find(s => s.id === activeSection)?.icon} />
				</svg>
				<span class="text-sm font-medium">{sections.find(s => s.id === activeSection)?.label}</span>
			</div>
			<svg
				class="w-4 h-4 text-surface-400 transition-transform duration-200 {mobileMenuOpen ? 'rotate-180' : ''}"
				fill="none" stroke="currentColor" viewBox="0 0 24 24"
			>
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
			</svg>
		</button>

		{#if mobileMenuOpen}
			<nav
				id="settings-nav-mobile"
				class="mt-2 card p-2"
				transition:slide={{ duration: 200 }}
			>
				{#each sections as section}
					<button
						class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors duration-150
							   {activeSection === section.id
								? 'bg-accent/10 text-accent'
								: 'text-surface-400 hover:bg-surface-800 hover:text-surface-200'}"
						onclick={() => selectSection(section.id)}
					>
						<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={section.icon} />
						</svg>
						<span class="text-sm">{section.label}</span>
					</button>
				{/each}
			</nav>
		{/if}
	</div>

	<!-- Desktop sidebar -->
	<aside class="hidden lg:block w-56 shrink-0">
		<nav class="card p-2 sticky top-6" aria-label="Settings navigation">
			{#each sections as section}
				<button
					class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors duration-150
						   {activeSection === section.id
							? 'bg-accent/10 text-accent'
							: 'text-surface-400 hover:bg-surface-800 hover:text-surface-200'}"
					onclick={() => activeSection = section.id}
					aria-current={activeSection === section.id ? 'page' : undefined}
				>
					<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={section.icon} />
					</svg>
					<span class="text-sm font-medium">{section.label}</span>
				</button>
			{/each}
		</nav>
	</aside>

	<!-- Content area -->
	<div class="flex-1 min-w-0 max-w-2xl">
		{#if activeSection === 'profile'}
			<div class="fade-in" >
				<div class="card">
					<h2 class="text-lg font-semibold mb-1">Profile</h2>
					<p class="text-sm text-surface-400 mb-6">Your public profile information.</p>

					<!-- Avatar -->
					<div class="flex items-start gap-5 mb-6 pb-6 border-b border-surface-700">
						<div class="relative group">
							<button
								class="w-20 h-20 rounded-xl overflow-hidden bg-surface-800 border-2 border-surface-600
									   flex items-center justify-center transition-all duration-200
									   group-hover:border-accent/50 focus-visible:outline focus-visible:outline-2
									   focus-visible:outline-offset-2 focus-visible:outline-accent cursor-pointer"
								onclick={handleAvatarClick}
								aria-label="Upload avatar"
							>
								{#if avatarPreview}
									<img src={avatarPreview} alt="Avatar preview" class="w-full h-full object-cover" />
								{:else}
									<svg class="w-8 h-8 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
									</svg>
								{/if}
								<!-- Hover overlay -->
								<div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center rounded-xl">
									<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
									</svg>
								</div>
							</button>
							<input
								bind:this={avatarInput}
								type="file"
								accept="image/*"
								class="hidden"
								onchange={handleAvatarChange}
								aria-label="Choose avatar file"
							/>
						</div>
						<div class="flex-1 pt-1">
							<p class="text-sm font-medium text-surface-200">Profile photo</p>
							<p class="text-xs text-surface-500 mt-1">JPG, PNG or GIF. Max 2MB.</p>
							<div class="flex gap-2 mt-3">
								<button class="btn-secondary text-xs px-3 py-1.5" onclick={handleAvatarClick}>
									Upload
								</button>
								{#if avatarPreview}
									<button
										class="text-xs px-3 py-1.5 rounded-lg text-red-400 hover:bg-red-500/10 transition-colors duration-150"
										onclick={removeAvatar}
									>
										Remove
									</button>
								{/if}
							</div>
						</div>
					</div>

					<!-- Form fields -->
					<form class="space-y-5" onsubmit={(e) => { e.preventDefault(); saveProfile(); }}>
						<!-- Name -->
						<div>
							<label for="profile-name" class="block text-sm font-medium text-surface-300 mb-1.5">
								Display name
							</label>
							<input
								id="profile-name"
								type="text"
								class="input w-full text-sm"
								placeholder="Your name"
								bind:value={profileName}
							/>
						</div>

						<!-- Email -->
						<div>
							<label for="profile-email" class="block text-sm font-medium text-surface-300 mb-1.5">
								Email address
							</label>
							<input
								id="profile-email"
								type="email"
								class="input w-full text-sm"
								placeholder="you@example.com"
								bind:value={profileEmail}
							/>
							<p class="text-xs text-surface-500 mt-1.5">Used for notifications and account recovery.</p>
						</div>

						<!-- Bio -->
						<div>
							<label for="profile-bio" class="block text-sm font-medium text-surface-300 mb-1.5">
								Bio
							</label>
							<textarea
								id="profile-bio"
								class="input w-full text-sm resize-none"
								rows="4"
								placeholder="Tell us a bit about yourself..."
								bind:value={profileBio}
							></textarea>
							<p class="text-xs text-surface-500 mt-1.5">{profileBio.length}/200 characters</p>
						</div>

						<!-- Save -->
						<div class="flex items-center justify-end gap-3 pt-2">
							<button type="button" class="btn-secondary text-sm">
								Cancel
							</button>
							<button
								type="submit"
								class="btn-primary text-sm inline-flex items-center gap-2"
								disabled={saving}
							>
								{#if saving}
									<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white/30 border-t-white"></span>
								{/if}
								{saving ? 'Saving...' : 'Save Changes'}
							</button>
						</div>
					</form>
				</div>
			</div>
		{:else if activeSection === 'account'}
			<div class="fade-in">
				<div class="space-y-6">
					<!-- Change password -->
					<div class="card">
						<h2 class="text-lg font-semibold mb-1">Change Password</h2>
						<p class="text-sm text-surface-400 mb-6">Update your password to keep your account secure.</p>

						<form class="space-y-5" onsubmit={(e) => e.preventDefault()}>
							<div>
								<label for="current-password" class="block text-sm font-medium text-surface-300 mb-1.5">
									Current password
								</label>
								<input
									id="current-password"
									type="password"
									class="input w-full text-sm"
									placeholder="Enter current password"
									bind:value={currentPassword}
								/>
							</div>

							<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
								<div>
									<label for="new-password" class="block text-sm font-medium text-surface-300 mb-1.5">
										New password
									</label>
									<input
										id="new-password"
										type="password"
										class="input w-full text-sm"
										placeholder="Enter new password"
										bind:value={newPassword}
									/>
								</div>
								<div>
									<label for="confirm-password" class="block text-sm font-medium text-surface-300 mb-1.5">
										Confirm password
									</label>
									<input
										id="confirm-password"
										type="password"
										class="input w-full text-sm"
										placeholder="Confirm new password"
										bind:value={confirmPassword}
									/>
								</div>
							</div>

							{#if newPassword && confirmPassword && newPassword !== confirmPassword}
								<div class="flex items-center gap-2 text-sm text-red-400">
									<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.27 16.5c-.77.833.192 2.5 1.732 2.5z" />
									</svg>
									Passwords do not match.
								</div>
							{/if}

							<div class="flex justify-end pt-2">
								<button type="submit" class="btn-primary text-sm">
									Update Password
								</button>
							</div>
						</form>
					</div>

					<!-- Sessions -->
					<div class="card">
						<h2 class="text-lg font-semibold mb-1">Active Sessions</h2>
						<p class="text-sm text-surface-400 mb-4">Manage devices where you're currently signed in.</p>

						<div class="divide-y divide-surface-700/50">
							<!-- Current session -->
							<div class="flex items-center justify-between py-3">
								<div class="flex items-center gap-3">
									<div class="w-9 h-9 rounded-lg bg-surface-800 flex items-center justify-center">
										<svg class="w-4.5 h-4.5 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
										</svg>
									</div>
									<div>
										<p class="text-sm font-medium text-surface-200">This device</p>
										<p class="text-xs text-surface-500">Last active: now</p>
									</div>
								</div>
								<span class="text-xs font-medium text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full">
									Current
								</span>
							</div>
						</div>
					</div>

					<!-- Danger zone -->
					<div class="card border-red-500/20">
						<h2 class="text-lg font-semibold text-red-400 mb-1">Danger Zone</h2>
						<p class="text-sm text-surface-400 mb-4">Irreversible actions. Proceed with caution.</p>

						<div class="flex items-center justify-between p-3 rounded-lg bg-red-500/5 border border-red-500/10">
							<div>
								<p class="text-sm font-medium text-surface-200">Delete account</p>
								<p class="text-xs text-surface-500">Permanently remove your account and all data.</p>
							</div>
							<button class="btn-danger text-sm px-3 py-1.5">
								Delete
							</button>
						</div>
					</div>
				</div>
			</div>
		{:else if activeSection === 'notifications'}
			<div class="fade-in">
				<div class="card">
					<h2 class="text-lg font-semibold mb-1">Notification Preferences</h2>
					<p class="text-sm text-surface-400 mb-6">Choose how and when you want to be notified.</p>

					<!-- Delivery channels -->
					<div class="mb-6">
						<h3 class="text-xs font-medium text-surface-500 uppercase tracking-wide mb-3">Delivery channels</h3>
						<div class="space-y-3">
							<!-- Email notifications toggle -->
							<div class="flex items-center justify-between p-3 rounded-lg bg-surface-800/50">
								<div class="flex items-center gap-3">
									<div class="w-9 h-9 rounded-lg bg-surface-700 flex items-center justify-center">
										<svg class="w-4.5 h-4.5 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
										</svg>
									</div>
									<div>
										<p class="text-sm font-medium text-surface-200">Email notifications</p>
										<p class="text-xs text-surface-500">Receive updates via email.</p>
									</div>
								</div>
								<button
									role="switch"
									aria-checked={emailNotifications}
									class="relative w-11 h-6 rounded-full transition-colors duration-200 {emailNotifications ? 'bg-accent' : 'bg-surface-700'}
										   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
									onclick={() => emailNotifications = !emailNotifications}
								>
									<div class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 {emailNotifications ? 'translate-x-5' : ''}"></div>
								</button>
							</div>

							<!-- Push notifications toggle -->
							<div class="flex items-center justify-between p-3 rounded-lg bg-surface-800/50">
								<div class="flex items-center gap-3">
									<div class="w-9 h-9 rounded-lg bg-surface-700 flex items-center justify-center">
										<svg class="w-4.5 h-4.5 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
										</svg>
									</div>
									<div>
										<p class="text-sm font-medium text-surface-200">Push notifications</p>
										<p class="text-xs text-surface-500">Browser push notifications.</p>
									</div>
								</div>
								<button
									role="switch"
									aria-checked={pushNotifications}
									class="relative w-11 h-6 rounded-full transition-colors duration-200 {pushNotifications ? 'bg-accent' : 'bg-surface-700'}
										   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
									onclick={() => pushNotifications = !pushNotifications}
								>
									<div class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 {pushNotifications ? 'translate-x-5' : ''}"></div>
								</button>
							</div>
						</div>
					</div>

					<!-- Event types -->
					<div>
						<h3 class="text-xs font-medium text-surface-500 uppercase tracking-wide mb-3">Events</h3>
						<div class="divide-y divide-surface-700/50">
							<!-- Print complete -->
							<div class="flex items-center justify-between py-3.5">
								<div>
									<p class="text-sm font-medium text-surface-200">Print completed</p>
									<p class="text-xs text-surface-500">When a print job finishes successfully.</p>
								</div>
								<button
									role="switch"
									aria-checked={printCompleteNotify}
									class="relative w-11 h-6 rounded-full transition-colors duration-200 {printCompleteNotify ? 'bg-accent' : 'bg-surface-700'}
										   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
									onclick={() => printCompleteNotify = !printCompleteNotify}
								>
									<div class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 {printCompleteNotify ? 'translate-x-5' : ''}"></div>
								</button>
							</div>

							<!-- Errors -->
							<div class="flex items-center justify-between py-3.5">
								<div>
									<p class="text-sm font-medium text-surface-200">Errors and failures</p>
									<p class="text-xs text-surface-500">When a print fails or the printer encounters an error.</p>
								</div>
								<button
									role="switch"
									aria-checked={errorNotify}
									class="relative w-11 h-6 rounded-full transition-colors duration-200 {errorNotify ? 'bg-accent' : 'bg-surface-700'}
										   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
									onclick={() => errorNotify = !errorNotify}
								>
									<div class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 {errorNotify ? 'translate-x-5' : ''}"></div>
								</button>
							</div>

							<!-- Software updates -->
							<div class="flex items-center justify-between py-3.5">
								<div>
									<p class="text-sm font-medium text-surface-200">Software updates</p>
									<p class="text-xs text-surface-500">When a new version of PrintForge is available.</p>
								</div>
								<button
									role="switch"
									aria-checked={updateNotify}
									class="relative w-11 h-6 rounded-full transition-colors duration-200 {updateNotify ? 'bg-accent' : 'bg-surface-700'}
										   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
									onclick={() => updateNotify = !updateNotify}
								>
									<div class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 {updateNotify ? 'translate-x-5' : ''}"></div>
								</button>
							</div>
						</div>
					</div>
				</div>
			</div>
		{:else if activeSection === 'appearance'}
			<div class="fade-in">
				<div class="card">
					<h2 class="text-lg font-semibold mb-1">Appearance</h2>
					<p class="text-sm text-surface-400 mb-6">Customize how PrintForge looks on your device.</p>

					<!-- Theme selection -->
					<div class="mb-8">
						<h3 class="text-xs font-medium text-surface-500 uppercase tracking-wide mb-3">Theme</h3>
						<div class="grid grid-cols-3 gap-3">
							<!-- Dark -->
							<button
								class="relative rounded-xl border-2 p-3 transition-all duration-200
									   {theme === 'dark'
										? 'border-accent bg-accent/5'
										: 'border-surface-700 hover:border-surface-500'}"
								onclick={() => theme = 'dark'}
							>
								<div class="rounded-lg bg-surface-900 border border-surface-700 p-2 mb-2.5">
									<div class="h-1.5 w-8 bg-surface-600 rounded mb-1.5"></div>
									<div class="h-1.5 w-12 bg-surface-700 rounded mb-1"></div>
									<div class="h-1.5 w-6 bg-surface-700 rounded"></div>
								</div>
								<span class="text-xs font-medium {theme === 'dark' ? 'text-accent' : 'text-surface-400'}">Dark</span>
								{#if theme === 'dark'}
									<div class="absolute top-2 right-2">
										<svg class="w-4 h-4 text-accent" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
										</svg>
									</div>
								{/if}
							</button>

							<!-- Light -->
							<button
								class="relative rounded-xl border-2 p-3 transition-all duration-200
									   {theme === 'light'
										? 'border-accent bg-accent/5'
										: 'border-surface-700 hover:border-surface-500'}"
								onclick={() => theme = 'light'}
							>
								<div class="rounded-lg bg-white border border-gray-200 p-2 mb-2.5">
									<div class="h-1.5 w-8 bg-gray-300 rounded mb-1.5"></div>
									<div class="h-1.5 w-12 bg-gray-200 rounded mb-1"></div>
									<div class="h-1.5 w-6 bg-gray-200 rounded"></div>
								</div>
								<span class="text-xs font-medium {theme === 'light' ? 'text-accent' : 'text-surface-400'}">Light</span>
								{#if theme === 'light'}
									<div class="absolute top-2 right-2">
										<svg class="w-4 h-4 text-accent" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
										</svg>
									</div>
								{/if}
							</button>

							<!-- System -->
							<button
								class="relative rounded-xl border-2 p-3 transition-all duration-200
									   {theme === 'system'
										? 'border-accent bg-accent/5'
										: 'border-surface-700 hover:border-surface-500'}"
								onclick={() => theme = 'system'}
							>
								<div class="rounded-lg overflow-hidden border border-surface-700 mb-2.5">
									<div class="flex h-[42px]">
										<div class="w-1/2 bg-white p-1.5">
											<div class="h-1 w-4 bg-gray-300 rounded mb-1"></div>
											<div class="h-1 w-6 bg-gray-200 rounded"></div>
										</div>
										<div class="w-1/2 bg-surface-900 p-1.5">
											<div class="h-1 w-4 bg-surface-600 rounded mb-1"></div>
											<div class="h-1 w-6 bg-surface-700 rounded"></div>
										</div>
									</div>
								</div>
								<span class="text-xs font-medium {theme === 'system' ? 'text-accent' : 'text-surface-400'}">System</span>
								{#if theme === 'system'}
									<div class="absolute top-2 right-2">
										<svg class="w-4 h-4 text-accent" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
										</svg>
									</div>
								{/if}
							</button>
						</div>
					</div>

					<!-- Font size -->
					<div>
						<h3 class="text-xs font-medium text-surface-500 uppercase tracking-wide mb-3">Font size</h3>
						<div class="flex items-center gap-2 p-1 bg-surface-800 rounded-lg w-fit">
							<button
								class="px-4 py-2 rounded-md text-xs font-medium transition-colors duration-150
									   {fontSize === 'small'
										? 'bg-surface-600 text-surface-100 shadow-sm'
										: 'text-surface-400 hover:text-surface-200'}"
								onclick={() => fontSize = 'small'}
							>
								Small
							</button>
							<button
								class="px-4 py-2 rounded-md text-sm font-medium transition-colors duration-150
									   {fontSize === 'default'
										? 'bg-surface-600 text-surface-100 shadow-sm'
										: 'text-surface-400 hover:text-surface-200'}"
								onclick={() => fontSize = 'default'}
							>
								Default
							</button>
							<button
								class="px-4 py-2 rounded-md text-base font-medium transition-colors duration-150
									   {fontSize === 'large'
										? 'bg-surface-600 text-surface-100 shadow-sm'
										: 'text-surface-400 hover:text-surface-200'}"
								onclick={() => fontSize = 'large'}
							>
								Large
							</button>
						</div>
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>
