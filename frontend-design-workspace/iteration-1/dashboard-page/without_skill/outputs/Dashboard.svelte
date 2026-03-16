<script>
  // Static demo data for the dashboard

  const stats = [
    {
      label: 'Total Users',
      value: '12,847',
      change: '+14.2%',
      changeType: 'positive',
      icon: 'users',
    },
    {
      label: 'Revenue',
      value: '$48,352',
      change: '+8.1%',
      changeType: 'positive',
      icon: 'revenue',
    },
    {
      label: 'Orders',
      value: '3,642',
      change: '-2.4%',
      changeType: 'negative',
      icon: 'orders',
    },
    {
      label: 'Conversion Rate',
      value: '3.24%',
      change: '+1.8%',
      changeType: 'positive',
      icon: 'conversion',
    },
  ];

  const recentOrders = [
    { id: 'ORD-7291', customer: 'Sarah Johnson', amount: '$249.99', status: 'Completed', date: '2026-03-16' },
    { id: 'ORD-7290', customer: 'Michael Chen', amount: '$89.50', status: 'Processing', date: '2026-03-16' },
    { id: 'ORD-7289', customer: 'Emily Davis', amount: '$432.00', status: 'Completed', date: '2026-03-15' },
    { id: 'ORD-7288', customer: 'James Wilson', amount: '$67.25', status: 'Shipped', date: '2026-03-15' },
    { id: 'ORD-7287', customer: 'Olivia Martinez', amount: '$185.75', status: 'Cancelled', date: '2026-03-14' },
    { id: 'ORD-7286', customer: 'Daniel Brown', amount: '$312.40', status: 'Completed', date: '2026-03-14' },
    { id: 'ORD-7285', customer: 'Sophia Lee', amount: '$156.00', status: 'Processing', date: '2026-03-13' },
    { id: 'ORD-7284', customer: 'William Taylor', amount: '$728.90', status: 'Shipped', date: '2026-03-13' },
  ];

  /**
   * Returns Tailwind classes for a given order status badge.
   * @param {string} status
   * @returns {string}
   */
  function statusClasses(status) {
    switch (status) {
      case 'Completed':
        return 'bg-green-100 text-green-700';
      case 'Processing':
        return 'bg-blue-100 text-blue-700';
      case 'Shipped':
        return 'bg-yellow-100 text-yellow-700';
      case 'Cancelled':
        return 'bg-red-100 text-red-700';
      default:
        return 'bg-gray-100 text-gray-700';
    }
  }
</script>

<div class="min-h-screen bg-gray-50 p-6 lg:p-10">
  <!-- Page Header -->
  <div class="mb-8">
    <h1 class="text-3xl font-bold text-gray-900">Dashboard</h1>
    <p class="mt-1 text-sm text-gray-500">Welcome back. Here's what's happening today.</p>
  </div>

  <!-- Stat Cards -->
  <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4 mb-8">
    {#each stats as stat}
      <div class="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60 transition hover:shadow-md">
        <div class="flex items-center justify-between">
          <span class="text-sm font-medium text-gray-500">{stat.label}</span>

          <!-- Icon -->
          <span class="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
            {#if stat.icon === 'users'}
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path d="M9 6a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm8 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm-4.07 11c.046-.327.07-.66.07-1a6.97 6.97 0 0 0-1.5-4.33A5 5 0 0 1 19 16v1h-6.07ZM6 11a5 5 0 0 1 5 5v1H1v-1a5 5 0 0 1 5-5Z" />
              </svg>
            {:else if stat.icon === 'revenue'}
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path d="M10.75 10.818a2.4 2.4 0 0 0-.86-.317 14 14 0 0 1-.891-.27 1 1 0 0 1-.37-.218.56.56 0 0 1-.129-.382c0-.2.082-.36.247-.478.165-.12.393-.18.684-.18.305 0 .54.066.706.197a.66.66 0 0 1 .263.483h1.39a1.7 1.7 0 0 0-.326-.933 2 2 0 0 0-.805-.614V7h-1.3v.884a2.48 2.48 0 0 0-.96.453c-.37.303-.555.719-.555 1.248 0 .537.17.95.508 1.24.339.29.832.52 1.48.69.382.1.666.21.852.332.186.121.28.286.28.494a.58.58 0 0 1-.254.494c-.17.125-.4.187-.693.187-.327 0-.58-.075-.761-.225a.83.83 0 0 1-.296-.556H8.2c.024.508.213.93.567 1.267.354.337.856.546 1.504.628V13h1.3v-.88a2.58 2.58 0 0 0 1.02-.486c.39-.316.585-.744.585-1.284 0-.558-.17-.98-.51-1.264a3.3 3.3 0 0 0-.915-.468ZM10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16Z" />
              </svg>
            {:else if stat.icon === 'orders'}
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M6 2a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7.414A2 2 0 0 0 15.414 6L12 2.586A2 2 0 0 0 10.586 2H6Zm2 10a1 1 0 1 0 0 2h4a1 1 0 1 0 0-2H8Zm-1-4a1 1 0 0 1 1-1h4a1 1 0 1 1 0 2H8a1 1 0 0 1-1-1Z" clip-rule="evenodd" />
              </svg>
            {:else}
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M12.577 4.878a.75.75 0 0 1 .919-.53l4.78 1.281a.75.75 0 0 1 .531.919l-1.281 4.78a.75.75 0 0 1-1.449-.387l.81-3.022a19.407 19.407 0 0 1-5.594 5.203c-2.292 1.482-4.823 2.36-7.293 2.36a.75.75 0 0 1 0-1.5c2.093 0 4.298-.768 6.373-2.11a17.907 17.907 0 0 0 5.052-4.712l-3.03.812a.75.75 0 0 1-.918-.53Z" clip-rule="evenodd" />
              </svg>
            {/if}
          </span>
        </div>

        <p class="mt-4 text-3xl font-semibold text-gray-900">{stat.value}</p>

        <p class="mt-2 flex items-center gap-1 text-sm font-medium {stat.changeType === 'positive' ? 'text-green-600' : 'text-red-600'}">
          {#if stat.changeType === 'positive'}
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M12.577 4.878a.75.75 0 0 1 .919-.53l4.78 1.281a.75.75 0 0 1 .531.919l-1.281 4.78a.75.75 0 0 1-1.449-.387l.81-3.022a19.407 19.407 0 0 1-5.594 5.203c-2.292 1.482-4.823 2.36-7.293 2.36a.75.75 0 0 1 0-1.5c2.093 0 4.298-.768 6.373-2.11a17.907 17.907 0 0 0 5.052-4.712l-3.03.812a.75.75 0 0 1-.918-.53Z" clip-rule="evenodd" />
            </svg>
          {:else}
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M1.22 5.222a.75.75 0 0 1 1.06 0L7 9.942l3.768-3.769a.75.75 0 0 1 1.113.058 20.908 20.908 0 0 1 3.813 7.254l1.574-2.727a.75.75 0 0 1 1.3.75l-2.475 4.286a.75.75 0 0 1-1.025.275l-4.287-2.475a.75.75 0 0 1 .75-1.3l2.71 1.565a19.422 19.422 0 0 0-3.013-5.78L7.53 11.533a.75.75 0 0 1-1.06 0l-5.25-5.25a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" />
            </svg>
          {/if}
          {stat.change}
          <span class="text-gray-400 font-normal">vs last month</span>
        </p>
      </div>
    {/each}
  </div>

  <!-- Line Chart Placeholder -->
  <div class="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60 mb-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-lg font-semibold text-gray-900">Revenue Overview</h2>
        <p class="text-sm text-gray-500">Monthly revenue for the current year</p>
      </div>
      <div class="flex gap-2">
        <button class="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white">Monthly</button>
        <button class="rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200 transition">Weekly</button>
        <button class="rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200 transition">Daily</button>
      </div>
    </div>

    <!-- Chart placeholder area -->
    <div class="relative h-64 w-full rounded-xl bg-gradient-to-b from-indigo-50/80 to-white border border-dashed border-indigo-200 flex items-center justify-center">
      <!-- Faux grid lines -->
      <div class="absolute inset-0 flex flex-col justify-between px-4 py-4 pointer-events-none">
        <div class="border-b border-gray-100 w-full"></div>
        <div class="border-b border-gray-100 w-full"></div>
        <div class="border-b border-gray-100 w-full"></div>
        <div class="border-b border-gray-100 w-full"></div>
        <div class="w-full"></div>
      </div>

      <!-- Faux SVG line to suggest chart shape -->
      <svg class="absolute inset-0 w-full h-full px-8 py-6" viewBox="0 0 800 200" preserveAspectRatio="none">
        <defs>
          <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#6366f1" stop-opacity="0.2" />
            <stop offset="100%" stop-color="#6366f1" stop-opacity="0" />
          </linearGradient>
        </defs>
        <!-- Area fill -->
        <path
          d="M0,160 C50,140 100,120 150,100 C200,80 250,90 300,70 C350,50 400,65 450,45 C500,25 550,55 600,40 C650,25 700,35 750,20 L800,15 L800,200 L0,200 Z"
          fill="url(#chartGradient)"
        />
        <!-- Line -->
        <path
          d="M0,160 C50,140 100,120 150,100 C200,80 250,90 300,70 C350,50 400,65 450,45 C500,25 550,55 600,40 C650,25 700,35 750,20 L800,15"
          fill="none"
          stroke="#6366f1"
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <!-- Data points -->
        <circle cx="0" cy="160" r="4" fill="#6366f1" />
        <circle cx="150" cy="100" r="4" fill="#6366f1" />
        <circle cx="300" cy="70" r="4" fill="#6366f1" />
        <circle cx="450" cy="45" r="4" fill="#6366f1" />
        <circle cx="600" cy="40" r="4" fill="#6366f1" />
        <circle cx="800" cy="15" r="4" fill="#6366f1" />
      </svg>

      <!-- Month labels -->
      <div class="absolute bottom-2 left-8 right-8 flex justify-between text-xs text-gray-400 pointer-events-none">
        <span>Jan</span>
        <span>Feb</span>
        <span>Mar</span>
        <span>Apr</span>
        <span>May</span>
        <span>Jun</span>
        <span>Jul</span>
        <span>Aug</span>
        <span>Sep</span>
        <span>Oct</span>
        <span>Nov</span>
        <span>Dec</span>
      </div>

      <!-- Overlay label -->
      <div class="z-10 flex flex-col items-center gap-1">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-indigo-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
        </svg>
        <span class="text-sm font-medium text-indigo-400">Chart Placeholder</span>
        <span class="text-xs text-gray-400">Integrate your preferred charting library</span>
      </div>
    </div>
  </div>

  <!-- Recent Orders Table -->
  <div class="rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60">
    <div class="flex items-center justify-between p-6 pb-4">
      <div>
        <h2 class="text-lg font-semibold text-gray-900">Recent Orders</h2>
        <p class="text-sm text-gray-500">Latest transactions across all channels</p>
      </div>
      <button class="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-200 transition">
        View All
      </button>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full text-left">
        <thead>
          <tr class="border-t border-gray-100">
            <th class="px-6 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500">Order ID</th>
            <th class="px-6 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500">Customer</th>
            <th class="px-6 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500">Amount</th>
            <th class="px-6 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500">Status</th>
            <th class="px-6 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500">Date</th>
          </tr>
        </thead>
        <tbody>
          {#each recentOrders as order}
            <tr class="border-t border-gray-50 hover:bg-gray-50/50 transition">
              <td class="px-6 py-4 text-sm font-medium text-indigo-600">{order.id}</td>
              <td class="px-6 py-4 text-sm text-gray-700">{order.customer}</td>
              <td class="px-6 py-4 text-sm font-medium text-gray-900">{order.amount}</td>
              <td class="px-6 py-4">
                <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium {statusClasses(order.status)}">
                  {order.status}
                </span>
              </td>
              <td class="px-6 py-4 text-sm text-gray-500">{order.date}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <!-- Table footer -->
    <div class="flex items-center justify-between border-t border-gray-100 px-6 py-4">
      <p class="text-sm text-gray-500">Showing {recentOrders.length} of 3,642 orders</p>
      <div class="flex gap-2">
        <button class="rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-50 transition">Previous</button>
        <button class="rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-50 transition">Next</button>
      </div>
    </div>
  </div>
</div>
