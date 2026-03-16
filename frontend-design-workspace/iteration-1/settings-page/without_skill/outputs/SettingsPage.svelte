<script>
  let activeSection = 'profile';

  const navItems = [
    { id: 'profile', label: 'Profile', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
    { id: 'account', label: 'Account', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
    { id: 'notifications', label: 'Notifications', icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' },
    { id: 'appearance', label: 'Appearance', icon: 'M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01' }
  ];

  // Profile form state
  let profileName = '';
  let profileEmail = '';
  let profileBio = '';
  let avatarPreview = null;
  let avatarFileName = '';
  let fileInput;

  // Notifications state
  let emailNotifications = true;
  let pushNotifications = false;
  let weeklyDigest = true;
  let mentionAlerts = true;

  // Appearance state
  let theme = 'light';
  let fontSize = 'medium';

  function handleAvatarUpload(event) {
    const file = event.target.files[0];
    if (file) {
      avatarFileName = file.name;
      const reader = new FileReader();
      reader.onload = (e) => {
        avatarPreview = e.target.result;
      };
      reader.readAsDataURL(file);
    }
  }

  function triggerFileInput() {
    fileInput.click();
  }

  function removeAvatar() {
    avatarPreview = null;
    avatarFileName = '';
    if (fileInput) fileInput.value = '';
  }

  function handleProfileSave() {
    alert('Profile saved successfully!');
  }

  function handleAccountSave() {
    alert('Account settings saved!');
  }

  function handleNotificationsSave() {
    alert('Notification preferences saved!');
  }

  function handleAppearanceSave() {
    alert('Appearance settings saved!');
  }
</script>

<div class="min-h-screen bg-gray-50">
  <!-- Header -->
  <header class="bg-white border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <h1 class="text-xl font-semibold text-gray-900">Settings</h1>
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center">
            <span class="text-white text-sm font-medium">U</span>
          </div>
        </div>
      </div>
    </div>
  </header>

  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex flex-col lg:flex-row gap-8">

      <!-- Sidebar Navigation -->
      <aside class="w-full lg:w-64 flex-shrink-0">
        <nav class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <ul class="divide-y divide-gray-100">
            {#each navItems as item}
              <li>
                <button
                  on:click={() => activeSection = item.id}
                  class="w-full flex items-center gap-3 px-4 py-3.5 text-left transition-colors duration-150
                    {activeSection === item.id
                      ? 'bg-indigo-50 text-indigo-700 border-l-4 border-indigo-600'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900 border-l-4 border-transparent'}"
                >
                  <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d={item.icon} />
                  </svg>
                  <span class="font-medium text-sm">{item.label}</span>
                </button>
              </li>
            {/each}
          </ul>
        </nav>
      </aside>

      <!-- Main Content Area -->
      <main class="flex-1 min-w-0">

        <!-- Profile Section -->
        {#if activeSection === 'profile'}
          <div class="bg-white rounded-xl shadow-sm border border-gray-200">
            <div class="px-6 py-5 border-b border-gray-200">
              <h2 class="text-lg font-semibold text-gray-900">Profile</h2>
              <p class="mt-1 text-sm text-gray-500">Manage your public profile information.</p>
            </div>

            <form on:submit|preventDefault={handleProfileSave} class="p-6 space-y-8">

              <!-- Avatar Upload -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-3">Profile Photo</label>
                <div class="flex items-center gap-6">
                  <div class="relative">
                    {#if avatarPreview}
                      <img
                        src={avatarPreview}
                        alt="Avatar preview"
                        class="w-20 h-20 rounded-full object-cover ring-2 ring-gray-200"
                      />
                    {:else}
                      <div class="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center ring-2 ring-gray-200">
                        <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                      </div>
                    {/if}
                  </div>
                  <div class="flex flex-col gap-2">
                    <div class="flex items-center gap-3">
                      <button
                        type="button"
                        on:click={triggerFileInput}
                        class="inline-flex items-center px-4 py-2 text-sm font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                      >
                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        Upload Photo
                      </button>
                      {#if avatarPreview}
                        <button
                          type="button"
                          on:click={removeAvatar}
                          class="inline-flex items-center px-4 py-2 text-sm font-medium text-red-600 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                        >
                          Remove
                        </button>
                      {/if}
                    </div>
                    <input
                      bind:this={fileInput}
                      type="file"
                      accept="image/*"
                      on:change={handleAvatarUpload}
                      class="hidden"
                    />
                    {#if avatarFileName}
                      <p class="text-xs text-gray-500">{avatarFileName}</p>
                    {:else}
                      <p class="text-xs text-gray-400">JPG, PNG or GIF. Max 2MB.</p>
                    {/if}
                  </div>
                </div>
              </div>

              <!-- Name Field -->
              <div>
                <label for="profile-name" class="block text-sm font-medium text-gray-700 mb-1.5">
                  Full Name
                </label>
                <input
                  id="profile-name"
                  type="text"
                  bind:value={profileName}
                  placeholder="Enter your full name"
                  class="w-full max-w-lg px-4 py-2.5 text-sm border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors duration-150"
                />
              </div>

              <!-- Email Field -->
              <div>
                <label for="profile-email" class="block text-sm font-medium text-gray-700 mb-1.5">
                  Email Address
                </label>
                <input
                  id="profile-email"
                  type="email"
                  bind:value={profileEmail}
                  placeholder="you@example.com"
                  class="w-full max-w-lg px-4 py-2.5 text-sm border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors duration-150"
                />
                <p class="mt-1.5 text-xs text-gray-400">This email will be visible on your public profile.</p>
              </div>

              <!-- Bio Field -->
              <div>
                <label for="profile-bio" class="block text-sm font-medium text-gray-700 mb-1.5">
                  Bio
                </label>
                <textarea
                  id="profile-bio"
                  bind:value={profileBio}
                  rows="4"
                  placeholder="Write a short bio about yourself..."
                  class="w-full max-w-lg px-4 py-2.5 text-sm border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors duration-150 resize-y"
                ></textarea>
                <p class="mt-1.5 text-xs text-gray-400">{profileBio.length} / 300 characters</p>
              </div>

              <!-- Save Button -->
              <div class="flex items-center gap-3 pt-4 border-t border-gray-100">
                <button
                  type="submit"
                  class="inline-flex items-center px-5 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  Save Changes
                </button>
                <button
                  type="button"
                  class="inline-flex items-center px-5 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 shadow-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-2"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        {/if}

        <!-- Account Section -->
        {#if activeSection === 'account'}
          <div class="bg-white rounded-xl shadow-sm border border-gray-200">
            <div class="px-6 py-5 border-b border-gray-200">
              <h2 class="text-lg font-semibold text-gray-900">Account</h2>
              <p class="mt-1 text-sm text-gray-500">Manage your account settings and security preferences.</p>
            </div>

            <form on:submit|preventDefault={handleAccountSave} class="p-6 space-y-8">

              <!-- Username -->
              <div>
                <label for="account-username" class="block text-sm font-medium text-gray-700 mb-1.5">
                  Username
                </label>
                <div class="flex items-center max-w-lg">
                  <span class="inline-flex items-center px-3 py-2.5 text-sm text-gray-500 bg-gray-50 border border-r-0 border-gray-300 rounded-l-lg">@</span>
                  <input
                    id="account-username"
                    type="text"
                    placeholder="username"
                    class="flex-1 px-4 py-2.5 text-sm border border-gray-300 rounded-r-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors duration-150"
                  />
                </div>
              </div>

              <!-- Change Password -->
              <div class="space-y-4">
                <h3 class="text-sm font-medium text-gray-900">Change Password</h3>
                <div>
                  <label for="current-password" class="block text-xs font-medium text-gray-600 mb-1">Current Password</label>
                  <input
                    id="current-password"
                    type="password"
                    placeholder="Enter current password"
                    class="w-full max-w-lg px-4 py-2.5 text-sm border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors duration-150"
                  />
                </div>
                <div>
                  <label for="new-password" class="block text-xs font-medium text-gray-600 mb-1">New Password</label>
                  <input
                    id="new-password"
                    type="password"
                    placeholder="Enter new password"
                    class="w-full max-w-lg px-4 py-2.5 text-sm border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors duration-150"
                  />
                </div>
                <div>
                  <label for="confirm-password" class="block text-xs font-medium text-gray-600 mb-1">Confirm New Password</label>
                  <input
                    id="confirm-password"
                    type="password"
                    placeholder="Confirm new password"
                    class="w-full max-w-lg px-4 py-2.5 text-sm border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors duration-150"
                  />
                </div>
              </div>

              <!-- Danger Zone -->
              <div class="rounded-lg border border-red-200 bg-red-50 p-5">
                <h3 class="text-sm font-semibold text-red-800">Danger Zone</h3>
                <p class="mt-1 text-sm text-red-600">Once you delete your account, there is no going back. Please be certain.</p>
                <button
                  type="button"
                  class="mt-4 inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 shadow-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                >
                  Delete Account
                </button>
              </div>

              <!-- Save Button -->
              <div class="flex items-center gap-3 pt-4 border-t border-gray-100">
                <button
                  type="submit"
                  class="inline-flex items-center px-5 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  Save Changes
                </button>
                <button
                  type="button"
                  class="inline-flex items-center px-5 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 shadow-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-2"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        {/if}

        <!-- Notifications Section -->
        {#if activeSection === 'notifications'}
          <div class="bg-white rounded-xl shadow-sm border border-gray-200">
            <div class="px-6 py-5 border-b border-gray-200">
              <h2 class="text-lg font-semibold text-gray-900">Notifications</h2>
              <p class="mt-1 text-sm text-gray-500">Choose how and when you want to be notified.</p>
            </div>

            <form on:submit|preventDefault={handleNotificationsSave} class="p-6 space-y-6">

              <!-- Toggle: Email Notifications -->
              <div class="flex items-center justify-between max-w-lg py-3">
                <div>
                  <h3 class="text-sm font-medium text-gray-900">Email Notifications</h3>
                  <p class="text-xs text-gray-500 mt-0.5">Receive email updates about activity on your account.</p>
                </div>
                <button
                  type="button"
                  on:click={() => emailNotifications = !emailNotifications}
                  class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2
                    {emailNotifications ? 'bg-indigo-600' : 'bg-gray-200'}"
                >
                  <span
                    class="inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform duration-200
                      {emailNotifications ? 'translate-x-6' : 'translate-x-1'}"
                  />
                </button>
              </div>

              <div class="border-t border-gray-100"></div>

              <!-- Toggle: Push Notifications -->
              <div class="flex items-center justify-between max-w-lg py-3">
                <div>
                  <h3 class="text-sm font-medium text-gray-900">Push Notifications</h3>
                  <p class="text-xs text-gray-500 mt-0.5">Receive push notifications in your browser.</p>
                </div>
                <button
                  type="button"
                  on:click={() => pushNotifications = !pushNotifications}
                  class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2
                    {pushNotifications ? 'bg-indigo-600' : 'bg-gray-200'}"
                >
                  <span
                    class="inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform duration-200
                      {pushNotifications ? 'translate-x-6' : 'translate-x-1'}"
                  />
                </button>
              </div>

              <div class="border-t border-gray-100"></div>

              <!-- Toggle: Weekly Digest -->
              <div class="flex items-center justify-between max-w-lg py-3">
                <div>
                  <h3 class="text-sm font-medium text-gray-900">Weekly Digest</h3>
                  <p class="text-xs text-gray-500 mt-0.5">Get a weekly summary of your activity and updates.</p>
                </div>
                <button
                  type="button"
                  on:click={() => weeklyDigest = !weeklyDigest}
                  class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2
                    {weeklyDigest ? 'bg-indigo-600' : 'bg-gray-200'}"
                >
                  <span
                    class="inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform duration-200
                      {weeklyDigest ? 'translate-x-6' : 'translate-x-1'}"
                  />
                </button>
              </div>

              <div class="border-t border-gray-100"></div>

              <!-- Toggle: Mention Alerts -->
              <div class="flex items-center justify-between max-w-lg py-3">
                <div>
                  <h3 class="text-sm font-medium text-gray-900">Mention Alerts</h3>
                  <p class="text-xs text-gray-500 mt-0.5">Get notified when someone mentions you.</p>
                </div>
                <button
                  type="button"
                  on:click={() => mentionAlerts = !mentionAlerts}
                  class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2
                    {mentionAlerts ? 'bg-indigo-600' : 'bg-gray-200'}"
                >
                  <span
                    class="inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform duration-200
                      {mentionAlerts ? 'translate-x-6' : 'translate-x-1'}"
                  />
                </button>
              </div>

              <!-- Save Button -->
              <div class="flex items-center gap-3 pt-4 border-t border-gray-100">
                <button
                  type="submit"
                  class="inline-flex items-center px-5 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  Save Preferences
                </button>
                <button
                  type="button"
                  class="inline-flex items-center px-5 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 shadow-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-2"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        {/if}

        <!-- Appearance Section -->
        {#if activeSection === 'appearance'}
          <div class="bg-white rounded-xl shadow-sm border border-gray-200">
            <div class="px-6 py-5 border-b border-gray-200">
              <h2 class="text-lg font-semibold text-gray-900">Appearance</h2>
              <p class="mt-1 text-sm text-gray-500">Customize how the application looks and feels.</p>
            </div>

            <form on:submit|preventDefault={handleAppearanceSave} class="p-6 space-y-8">

              <!-- Theme Selector -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-3">Theme</label>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-lg">
                  <!-- Light -->
                  <button
                    type="button"
                    on:click={() => theme = 'light'}
                    class="relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-150
                      {theme === 'light' ? 'border-indigo-600 bg-indigo-50 ring-1 ring-indigo-600' : 'border-gray-200 hover:border-gray-300 bg-white'}"
                  >
                    <div class="w-12 h-12 rounded-lg bg-white border border-gray-200 shadow-sm flex items-center justify-center">
                      <svg class="w-6 h-6 text-yellow-500" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 2.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM7.5 12a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM18.894 6.166a.75.75 0 00-1.06-1.06l-1.591 1.59a.75.75 0 101.06 1.061l1.591-1.59zM21.75 12a.75.75 0 01-.75.75h-2.25a.75.75 0 010-1.5H21a.75.75 0 01.75.75zM17.834 18.894a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 10-1.061 1.06l1.59 1.591zM12 18a.75.75 0 01.75.75V21a.75.75 0 01-1.5 0v-2.25A.75.75 0 0112 18zM7.758 17.303a.75.75 0 00-1.061-1.06l-1.591 1.59a.75.75 0 001.06 1.061l1.591-1.59zM6 12a.75.75 0 01-.75.75H3a.75.75 0 010-1.5h2.25A.75.75 0 016 12zM6.697 7.757a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 00-1.061 1.06l1.59 1.591z" />
                      </svg>
                    </div>
                    <span class="text-xs font-medium {theme === 'light' ? 'text-indigo-700' : 'text-gray-600'}">Light</span>
                    {#if theme === 'light'}
                      <div class="absolute top-2 right-2">
                        <svg class="w-4 h-4 text-indigo-600" fill="currentColor" viewBox="0 0 20 20">
                          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd" />
                        </svg>
                      </div>
                    {/if}
                  </button>

                  <!-- Dark -->
                  <button
                    type="button"
                    on:click={() => theme = 'dark'}
                    class="relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-150
                      {theme === 'dark' ? 'border-indigo-600 bg-indigo-50 ring-1 ring-indigo-600' : 'border-gray-200 hover:border-gray-300 bg-white'}"
                  >
                    <div class="w-12 h-12 rounded-lg bg-gray-800 border border-gray-700 shadow-sm flex items-center justify-center">
                      <svg class="w-6 h-6 text-gray-300" fill="currentColor" viewBox="0 0 24 24">
                        <path fill-rule="evenodd" d="M9.528 1.718a.75.75 0 01.162.819A8.97 8.97 0 009 6a9 9 0 009 9 8.97 8.97 0 003.463-.69.75.75 0 01.981.98 10.503 10.503 0 01-9.694 6.46c-5.799 0-10.5-4.701-10.5-10.5 0-4.368 2.667-8.112 6.46-9.694a.75.75 0 01.818.162z" clip-rule="evenodd" />
                      </svg>
                    </div>
                    <span class="text-xs font-medium {theme === 'dark' ? 'text-indigo-700' : 'text-gray-600'}">Dark</span>
                    {#if theme === 'dark'}
                      <div class="absolute top-2 right-2">
                        <svg class="w-4 h-4 text-indigo-600" fill="currentColor" viewBox="0 0 20 20">
                          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd" />
                        </svg>
                      </div>
                    {/if}
                  </button>

                  <!-- System -->
                  <button
                    type="button"
                    on:click={() => theme = 'system'}
                    class="relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-150
                      {theme === 'system' ? 'border-indigo-600 bg-indigo-50 ring-1 ring-indigo-600' : 'border-gray-200 hover:border-gray-300 bg-white'}"
                  >
                    <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-white to-gray-800 border border-gray-300 shadow-sm flex items-center justify-center">
                      <svg class="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" />
                      </svg>
                    </div>
                    <span class="text-xs font-medium {theme === 'system' ? 'text-indigo-700' : 'text-gray-600'}">System</span>
                    {#if theme === 'system'}
                      <div class="absolute top-2 right-2">
                        <svg class="w-4 h-4 text-indigo-600" fill="currentColor" viewBox="0 0 20 20">
                          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd" />
                        </svg>
                      </div>
                    {/if}
                  </button>
                </div>
              </div>

              <!-- Font Size -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-3">Font Size</label>
                <div class="flex items-center gap-3 max-w-lg">
                  {#each ['small', 'medium', 'large'] as size}
                    <button
                      type="button"
                      on:click={() => fontSize = size}
                      class="flex-1 px-4 py-2.5 text-sm font-medium rounded-lg border-2 transition-all duration-150
                        {fontSize === size
                          ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                          : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'}"
                    >
                      <span class="{size === 'small' ? 'text-xs' : size === 'large' ? 'text-base' : 'text-sm'}">
                        {size.charAt(0).toUpperCase() + size.slice(1)}
                      </span>
                    </button>
                  {/each}
                </div>
              </div>

              <!-- Save Button -->
              <div class="flex items-center gap-3 pt-4 border-t border-gray-100">
                <button
                  type="submit"
                  class="inline-flex items-center px-5 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  Save Changes
                </button>
                <button
                  type="button"
                  class="inline-flex items-center px-5 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 shadow-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-2"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        {/if}

      </main>
    </div>
  </div>
</div>
