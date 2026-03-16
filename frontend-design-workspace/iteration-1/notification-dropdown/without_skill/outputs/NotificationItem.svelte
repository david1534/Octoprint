<script>
  import { createEventDispatcher } from "svelte";

  export let notification;

  const dispatch = createEventDispatcher();

  function formatTimestamp(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) return "just now";
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  }

  function handleClick() {
    dispatch("read", notification.id);
  }

  const iconMap = {
    success: {
      path: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
      color: "text-green-500",
      bg: "bg-green-50",
    },
    error: {
      path: "M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z",
      color: "text-red-500",
      bg: "bg-red-50",
    },
    warning: {
      path: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z",
      color: "text-amber-500",
      bg: "bg-amber-50",
    },
    info: {
      path: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
      color: "text-blue-500",
      bg: "bg-blue-50",
    },
  };

  $: icon = iconMap[notification.type] || iconMap.info;
</script>

<button
  class="w-full text-left px-4 py-3 flex items-start gap-3 transition-colors duration-150 hover:bg-gray-50
         {notification.read ? 'opacity-60' : ''}"
  on:click={handleClick}
>
  <!-- Type icon -->
  <div class="flex-shrink-0 mt-0.5 rounded-full p-1.5 {icon.bg}">
    <svg
      xmlns="http://www.w3.org/2000/svg"
      class="h-4 w-4 {icon.color}"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      stroke-width="2"
    >
      <path stroke-linecap="round" stroke-linejoin="round" d={icon.path} />
    </svg>
  </div>

  <!-- Content -->
  <div class="flex-1 min-w-0">
    <div class="flex items-start justify-between gap-2">
      <p
        class="text-sm leading-snug {notification.read
          ? 'text-gray-500 font-normal'
          : 'text-gray-900 font-medium'}"
      >
        {notification.title}
      </p>

      <!-- Unread indicator dot -->
      {#if !notification.read}
        <span class="flex-shrink-0 mt-1.5">
          <span class="block h-2 w-2 rounded-full bg-blue-500"></span>
        </span>
      {/if}
    </div>

    {#if notification.message}
      <p class="text-xs text-gray-400 mt-0.5 line-clamp-2 leading-relaxed">
        {notification.message}
      </p>
    {/if}

    <p class="text-xs text-gray-400 mt-1">
      {formatTimestamp(notification.timestamp)}
    </p>
  </div>
</button>
