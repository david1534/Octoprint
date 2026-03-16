<script lang="ts">
	import { printerState } from '../stores/printer';

	let state = $derived($printerState);
</script>

<div class="card">
	<h3 class="text-sm font-medium text-surface-400 mb-3">Quick Stats</h3>
	<div class="space-y-2 text-sm">
		<div class="flex justify-between">
			<span class="text-surface-500">Hotend</span>
			<span class="tabular-nums text-surface-200">
				{state.hotend.actual.toFixed(1)}°C
				{#if state.hotend.target > 0}
					<span class="text-surface-500">/ {state.hotend.target.toFixed(0)}°C</span>
				{/if}
			</span>
		</div>
		<div class="flex justify-between">
			<span class="text-surface-500">Bed</span>
			<span class="tabular-nums text-surface-200">
				{state.bed.actual.toFixed(1)}°C
				{#if state.bed.target > 0}
					<span class="text-surface-500">/ {state.bed.target.toFixed(0)}°C</span>
				{/if}
			</span>
		</div>
		<div class="flex justify-between">
			<span class="text-surface-500">Position</span>
			<span class="tabular-nums text-surface-200">
				X:{state.position.x} Y:{state.position.y} Z:{state.position.z}
			</span>
		</div>
		<div class="flex justify-between">
			<span class="text-surface-500">Fan</span>
			<span class="text-surface-200">{Math.round(state.fan_speed / 2.55)}%</span>
		</div>
		{#if state.firmware}
			<div class="flex justify-between">
				<span class="text-surface-500">Firmware</span>
				<span class="text-surface-200 truncate max-w-[150px]">{state.firmware}</span>
			</div>
		{/if}
	</div>
</div>
