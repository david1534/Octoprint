<script>
  import { onMount, onDestroy } from "svelte";
  import NotificationItem from "./NotificationItem.svelte";

  // Notifications array - can be passed as a prop or managed internally.
  // Each notification: { id, title, message?, type: 'success'|'error'|'warning'|'info', timestamp, read }
  export let notifications = [
    {
      id: 1,
      title: "Print completed",
      message: "benchy_v2.gcode finished printing successfully.",
      type: "success",
      timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      read: false,
    },
    {
      id: 2,
      title: "Filament running low",
      message: "PLA White spool is estimated at 12% remaining.",
      type: "warning",
      timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
      read: false,
    },
    {
      id: 3,
      title: "Firmware update available",
      message: "Ender 3 firmware v4.2.7 is ready to install.",
      type: "info",
      timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
      read: false,
    },
    {
      id: 4,
      title: "Print failed",
      message: "gear_housing.gcode stopped unexpectedly at layer 42.",
      type: "error",
      timestamp: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
      read: true,
    },
    {
      id: 5,
      title: "Bed leveling complete",
      message: "Automatic mesh leveling finished with 0.02mm variance.",
      type: "success",
      timestamp: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
      read: true,
    },
  ];

  let isOpen = false;
  let dropdownRef;

  $: unreadCount = notifications.filter((n) => !n.read).length;

  function toggleDropdown() {
    isOpen = !isOpen;
  }

  function markAllAsRead() {
    notifications = notifications.map((n) => ({ ...n, read: true }));
  }

  function markAsRead(event) {
    const id = event.detail;
    notifications = notifications.map((n) =>
      n.id === id ? { ...n, read: true } : n
    );
  }

  function handleClickOutside(event) {
    if (dropdownRef && !dropdownRef.contains(event.target)) {
      isOpen = false;
    }
  }

  function handleKeydown(event) {
    if (event.key === "Escape") {
      isOpen = false;
    }
  }

  onMount(() => {
    document.addEventListener("click", handleClickOutside, true);
    document.addEventListener("keydown", handleKeydown);
  });

  onDestroy(() => {
    document.removeEventListener("click", handleClickOutside, true);
    document.removeEventListener("keydown", handleKeydown);
  });
</script>

<div class="relative" bind:this={dropdownRef}>
  <!-- Bell icon trigger button -->
  <button
    class="relative p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100
           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
           transition-colors duration-150"
    on:click={toggleDropdown}
    aria-label="Notifications"
    aria-expanded={isOpen}
    aria-haspopup="true"
  >
    <!-- Bell SVG icon -->
    <svg
      xmlns="http://www.w3.org/2000/svg"
      class="h-6 w-6"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      stroke-width="1.5"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
      />
    </svg>

    <!-- Unread badge -->
    {#if unreadCount > 0}
      <span
        class="absolute -top-0.5 -right-0.5 flex items-center justify-center h-5 min-w-[1.25rem]
               rounded-full bg-red-500 text-white text-xs font-bold px-1
               ring-2 ring-white"
      >
        {unreadCount > 99 ? "99+" : unreadCount}
      </span>
    {/if}
  </button>

  <!-- Dropdown panel -->
  {#if isOpen}
    <div
      class="absolute right-0 mt-2 w-96 max-h-[28rem] bg-white rounded-xl shadow-xl
             ring-1 ring-black/5 overflow-hidden z-50
             flex flex-col"
      role="menu"
    >
      <!-- Header -->
      <div
        class="flex items-center justify-between px-4 py-3 border-b border-gray-100"
      >
        <div class="flex items-center gap-2">
          <h3 class="text-sm font-semibold text-gray-900">Notifications</h3>
          {#if unreadCount > 0}
            <span
              class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700"
            >
              {unreadCount} new
            </span>
          {/if}
        </div>

        {#if unreadCount > 0}
          <button
            class="text-xs font-medium text-blue-600 hover:text-blue-800
                   transition-colors duration-150 focus:outline-none focus:underline"
            on:click={markAllAsRead}
          >
            Mark all as read
          </button>
        {/if}
      </div>

      <!-- Notification list -->
      <div class="overflow-y-auto flex-1 divide-y divide-gray-50">
        {#if notifications.length === 0}
          <div class="px-4 py-10 text-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-10 w-10 mx-auto text-gray-300 mb-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              stroke-width="1.5"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
              />
            </svg>
            <p class="text-sm text-gray-400">No notifications yet</p>
          </div>
        {:else}
          {#each notifications as notification (notification.id)}
            <NotificationItem {notification} on:read={markAsRead} />
          {/each}
        {/if}
      </div>

      <!-- Footer -->
      {#if notifications.length > 0}
        <div class="border-t border-gray-100 px-4 py-2.5">
          <button
            class="w-full text-center text-xs font-medium text-gray-500 hover:text-gray-700
                   transition-colors duration-150 focus:outline-none focus:underline"
          >
            View all notifications
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>
